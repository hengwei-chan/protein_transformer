""" Loss functions for training protein structure prediction models. """

import numpy as np
import prody as pr
import torch
import wandb

import protein_transformer.protein.Structure
from protein_transformer.protein.Sequence import VOCAB
from protein_transformer.protein.Structure import NUM_PREDICTED_ANGLES, \
    NUM_PREDICTED_COORDS, SC_ANGLES_START_POS
from .protein.structure_utils import get_backbone_from_full_coords


def combine_drmsd_mse(d, mse, w=.5, lndrmsd_norm=0.02, mse_norm=0.01, log=True):
    """
    Returns a combination of drmsd and mse loss that first normalizes their
    zscales, and then computes w * drmsd + (1 - w) * mse.
    """
    d = w * (d / lndrmsd_norm)
    mse = (1 - w) * (mse / mse_norm)
    if log: wandb.log({"MSE Weight": mse, "DRMSD Weight": d}, commit=False)
    return d + mse


def inverse_trig_transform(t):
    """
    Given a (BATCH x L X NUM_PREDICTED_ANGLES ) tensor, returns (BATCH X
    L X NUM_PREDICTED_ANGLES) tensor. Performs atan2 transformation from sin
    and cos values.
    """
    t = t.view(t.shape[0], -1, NUM_PREDICTED_ANGLES, 2)
    t_cos = t[:, :, :, 0]
    t_sin = t[:, :, :, 1]
    t = torch.atan2(t_sin, t_cos)
    return t


def remove_sos_eos_from_input(input_seq):
    """
    Given a sequence of integers that may be surrounded with EOS/SOS characters,
    returns the sequence without those characters.
    """
    start_idx = 1 if input_seq[0] == VOCAB.sos_id else 0
    end_idx = -1 if input_seq[-1] == VOCAB.eos_id else None
    return input_seq[start_idx : end_idx]


def drmsd_work(pred_ang, true_crd, input_seq, return_rmsd, do_backward=True, backbone_only=False, comparison="mse",
               pseudohuber_threshold=None):
    """
    A version of drmsd loss meant to be used in parallel. Operates on a tuple
    of predicted angles, coordinates, and sequence. Works for 1 protein at a
    time.
    """
    # Move numpy arrays to torch tensors
    pred_ang, true_crd, input_seq = torch.tensor(pred_ang), torch.tensor(true_crd), torch.tensor(input_seq)

    # Record leaf-node pointer to access gradients at end
    pred_ang.requires_grad_()
    starting_ang = pred_ang

    # Remove batch-level masking
    batch_mask = input_seq.ne(VOCAB.pad_id)
    input_seq = input_seq[batch_mask]
    true_crd = true_crd[:input_seq.shape[0] * NUM_PREDICTED_COORDS]

    # Compute coordinates
    pred_crd = angles_to_coords(pred_ang, input_seq)
    if backbone_only:
        pred_crd = get_backbone_from_full_coords(pred_crd)
        true_crd = get_backbone_from_full_coords(true_crd)

    # Remove coordinate-level masking for missing atoms
    true_crd_non_nan = torch.isnan(true_crd).eq(0)
    pred_crds_masked = pred_crd[true_crd_non_nan].reshape(-1, 3)
    true_crds_masked = true_crd[true_crd_non_nan].reshape(-1, 3)

    # Compute drmsd between existing atoms only
    losses = drmsd_all_methods(pred_crds_masked, true_crds_masked, pseudohuber_threshold)
    loss = losses[comparison]
    l_normed = loss / pred_crds_masked.shape[0]

    ret_losses = {"drmsd" : losses["mse"].item(),
                  "pseudohuber" : losses["pseudohuber"].item(),
                  "modified-pseudohuber" : losses["modified-pseudohuber"].item(),
                  "ln-drmsd": losses["mse"].item() / pred_crds_masked.shape[0],
                  "ln-pseudohuber": losses["pseudohuber"].item() / pred_crds_masked.shape[0],
                  "ln-modified-pseudohuber": losses["modified-pseudohuber"].item() / pred_crds_masked.shape[0],
                  "rmsd": rmsd(pred_crds_masked.data.numpy(), true_crds_masked.data.numpy()) if return_rmsd else None
                  }

    # Repeat above for bb only
    pred_crd_bb = get_backbone_from_full_coords(pred_crd)
    true_crd_bb = get_backbone_from_full_coords(true_crd)
    true_crd_bb_non_nan = torch.isnan(true_crd_bb).eq(0)
    pred_crd_bb_masked = pred_crd_bb[true_crd_bb_non_nan].reshape(-1, 3)
    true_crd_bb_masked = true_crd_bb[true_crd_bb_non_nan].reshape(-1, 3)
    bb_loss = drmsd(pred_crd_bb_masked, true_crd_bb_masked, comparison="mse")
    bb_loss_normed = bb_loss / pred_crd_bb_masked.shape[0]

    ret_losses["bb-drmsd"] = bb_loss.item()
    ret_losses["ln-bb-drmsd"] = bb_loss_normed.item()

    if do_backward:
        l_normed.backward()

    return starting_ang.grad, ret_losses


def angles_to_coords(angles, seq, remove_batch_padding=False):
    """
    Convert torsional angles to coordinates.
    """
    pred_ang, input_seq = angles, seq
    if remove_batch_padding:
        # Remove batch-level masking
        batch_mask = input_seq.ne(VOCAB.pad_id)
        input_seq = input_seq[batch_mask]

    # Remove SOS and EOS characters if present
    input_seq = remove_sos_eos_from_input(input_seq)
    pred_ang = pred_ang[:input_seq.shape[0]]

    # Generate coordinates
    return protein_transformer.protein.Structure.generate_coords(pred_ang, input_seq, torch.device("cpu"))


def parallel_coords_only(ang, seq):
    coords = angles_to_coords(ang, seq)
    return coords

def drmsd_work_wrapper(ang_crd_seq_retrmsd_doback_bbonly_comparison_thresh):
    """
    Unpacks arguments for the drmsd_work function. Useful for Pool.map().
    Parameters
    ----------
    ang_crd_seq_retrmsd_doback_bbonly_comparison : tuple
    """
    ang, crd, seq, return_rmsd, do_backward,\
    backbone_only, comparison, threshold = ang_crd_seq_retrmsd_doback_bbonly_comparison_thresh
    return drmsd_work(ang, crd, seq, return_rmsd, do_backward, backbone_only, comparison, threshold)

def compute_batch_drmsd(pred_angs, true_crds, input_seqs, device=torch.device("cpu"), return_rmsd=False,
                        do_backward=False, retain_graph=False, pool=None, backbone_only=False,
                        comparison="mse", pseudohuber_threshold=10):
    """
    Calculate DRMSD loss by first generating predicted coordinates from
    angles. Then, predicted coordinates are compared with the true coordinate
    tensor provided to the function.
    """
    pred_angs, true_crds, input_seqs = pred_angs.to(device), true_crds.to(device), input_seqs.to(device)
    pred_angs = inverse_trig_transform(pred_angs)

    # Compute drmsd in parallel over the batch
    if pool is not None:
        results = pool.map(drmsd_work_wrapper, zip(pred_angs.detach().numpy(), true_crds.detach().numpy(),
                                                   input_seqs.detach().numpy(), [return_rmsd]*pred_angs.shape[0],
                                                   [do_backward]*pred_angs.shape[0], [backbone_only]*pred_angs.shape[0],
                                                   [comparison]*pred_angs.shape[0],
                                                   [pseudohuber_threshold]*pred_angs.shape[0]))
    else:
        results = (drmsd_work(ang.detach(), crd.detach(), seq.detach(), return_rmsd, do_backward, backbone_only,
                              comparison, pseudohuber_threshold)
                              for ang, crd, seq in zip(pred_angs, true_crds, input_seqs))

    # Unpack the multiprocessing results
    grads, drmsds, ln_drmsds, bb_drmsds, bb_ln_drmsds, rmsds = [], [], [], [], [], []
    pseudohubers, modpseudohubers, ln_pseudohubers, ln_modpseudohubers = [], [], [], []
    for r in results:
        grad, loss_dict = r
        d, ln_d, bb_d, bb_ln_d, rmsd_val = loss_dict["drmsd"], loss_dict["ln-drmsd"], loss_dict["bb-drmsd"], \
                                       loss_dict["ln-bb-drmsd"], loss_dict["rmsd"]
        ph, ln_ph = loss_dict["pseudohuber"], loss_dict["ln-pseudohuber"]
        mph, ln_mph = loss_dict["modified-pseudohuber"], loss_dict["ln-modified-pseudohuber"]

        grads.append(grad)
        drmsds.append(d)
        ln_drmsds.append(ln_d)
        bb_drmsds.append(bb_d)
        bb_ln_drmsds.append(bb_ln_d)
        pseudohubers.append(ph)
        modpseudohubers.append(mph)
        ln_pseudohubers.append(ln_ph)
        ln_modpseudohubers.append(ln_mph)

        if rmsd_val:
            rmsds.append(rmsd_val)

    if do_backward:
        pred_angs.backward(gradient=torch.stack(grads), retain_graph=retain_graph)

    ret_losses = {"drmsd": np.mean(drmsds),
                  "ln-drmsd": np.mean(ln_drmsds),
                  "bb-drmsd": np.mean(bb_drmsds),
                  "ln-bb-drmsd": np.mean(bb_ln_drmsds),
                  "pseudohuber": np.mean(pseudohubers),
                  "modified-pseudohuber": np.mean(modpseudohubers),
                  "ln-pseudohuber": np.mean(ln_pseudohubers),
                  "ln-modified-pseudohuber": np.mean(ln_modpseudohubers),
                  "rmsd": np.mean(rmsds) if len(rmsds) > 0 else None}

    return ret_losses



def mse_over_angles(pred, true, bb_only=False, sc_only=False):
    """Returns the mean squared error between two tensor batches.

    Given a predicted angle tensor and a true angle tensor (batch-padded with
    zeros, and missing-item-padded with nans), this function first removes
    batch then item padding before using torch's built-in MSE loss function.

    Args:
        pred, true (np.ndarray): 4-dimensional tensors

    Returns:
        MSE loss between true and pred.
    """
    assert len(pred.shape) == 3, "This function must operate on a batch of angles."

    # Slice off appropriate angles for evaluation, depending on whether or not
    # the input is in sin/cos terms, or radians
    if bb_only and pred.shape[-1] == NUM_PREDICTED_ANGLES * 2:
        pred = pred[:,:,:SC_ANGLES_START_POS*2]
        true = true[:,:,:SC_ANGLES_START_POS*2]
    elif bb_only and pred.shape[-1] == NUM_PREDICTED_ANGLES:
        pred = pred[:,:,:SC_ANGLES_START_POS]
        true = true[:,:,:SC_ANGLES_START_POS]
    elif sc_only and pred.shape[-1] == NUM_PREDICTED_ANGLES * 2:
        pred = pred[:,:,SC_ANGLES_START_POS * 2:]
        true = true[:,:,SC_ANGLES_START_POS * 2:]
    elif sc_only and pred.shape[-1] == NUM_PREDICTED_ANGLES:
        pred = pred[:, :, SC_ANGLES_START_POS:]
        true = true[:, :, SC_ANGLES_START_POS:]
    elif not (not bb_only and not sc_only):
        print(pred.shape)
        raise Exception("Unknown angle tensor shape.")

    # Remove batch padding
    ang_non_zero = true.ne(0).any(dim=2)
    tgt_ang_non_zero = true[ang_non_zero]

    # Remove missing angles
    ang_non_nans = torch.isnan(tgt_ang_non_zero).eq(0)
    return torch.nn.functional.mse_loss(pred[ang_non_zero][ang_non_nans], true[ang_non_zero][ang_non_nans])


def mse_over_angles_numpy(pred, true):
    """ Numpy version of mse_over_angles.

    Given a predicted angle tensor and a true angle tensor (batch-padded with
    zeros, and missing-item-padded with nans), this function first removes
    batch then item padding before using torch's built-in MSE loss function.

    Args:
        pred true (np.ndarray): 4-dimensional tensors

    Returns:
        MSE loss between true and pred.
    """
    return mse_over_angles(torch.tensor(pred), torch.tensor(true)).numpy()


def pairwise_internal_dist(x):
    """ Returns all pairwise distances between points in a coordinate tensor.

    An implementation of cdist (pairwise distances between sets of vectors)
    from user jacobrgardner on github. Not implemented for batches.
    https://github.com/pytorch/pytorch/issues/15253

    Args:
        x (torch.Tensor): coordinate tensor with shape (L x 3)

    Returns:
        res (torch.Tensor): a distance tensor comparing all (L x L) pairs of
                            points
    """
    x1, x2 = x, x
    assert len(x1.shape) == 2, "Pairwise internal distance method is not " \
                               "implemented for batches."
    x1_norm = x1.pow(2).sum(dim=-1, keepdim=True)  # TODO: experiment with alternative to pow, remove duplicated norm
    res = torch.addmm(x1_norm.transpose(-2, -1), x1, x2.transpose(-2, -1), alpha=-2).add_(x1_norm)
    res = res.clamp_min_(1e-30).sqrt_()
    return res


def drmsd(a, b, comparison="mse", pseudohuber_threshold=None):
    """ Returns distance root-mean-squared-deviation between tensors a and b.

    Given 2 coordinate tensors, returns the dRMSD between them. Both
    tensors must be the exact same shape. It works by creating a mask of the
    upper-triangular indices of the pairwise distance matrix (excluding the
    diagonal). Then, the resulting values are compared with Pytorch's MSE loss.

    Args:
        a, b (torch.Tensor): coordinate tensor with shape (L x 3).

    Returns:
        res (torch.Tensor): DRMSD between a and b.
    """

    a_ = pairwise_internal_dist(a)
    b_ = pairwise_internal_dist(b)

    i = torch.triu_indices(a_.shape[0], a_.shape[1], offset=1)
    if comparison == "mse":
        mse = torch.nn.functional.mse_loss(a_[i[0], i[1]].float(), b_[i[0], i[1]].float())
        res = torch.sqrt(mse)
    elif comparison == "pseudohuber":
        res = pseudohuber(a_[i[0], i[1]].float(), b_[i[0], i[1]].float(), pseudohuber_threshold)
    elif comparison == "modified-pseudohuber":
        res = modified_pseudohuber(a_[i[0], i[1]].float(), b_[i[0], i[1]].float(), pseudohuber_threshold)
    else:
        raise NotImplementedError(f"{comparison} is not recognized as a valid DRMSD comparison method.")

    return res


def drmsd_all_methods(a, b, pseudohuber_threshold=None):
    """ Returns distance root-mean-squared-deviation between tensors a and b.

    Given 2 coordinate tensors, returns the dRMSD between them. Both
    tensors must be the exact same shape. It works by creating a mask of the
    upper-triangular indices of the pairwise distance matrix (excluding the
    diagonal). Then, the resulting values are compared with Pytorch's MSE loss.

    Args:
        a, b (torch.Tensor): coordinate tensor with shape (L x 3).

    Returns:
        res (torch.Tensor): DRMSD between a and b.
    """

    a_ = pairwise_internal_dist(a)
    b_ = pairwise_internal_dist(b)

    i = torch.triu_indices(a_.shape[0], a_.shape[1], offset=1)

    results = {}
    results["mse"] = torch.sqrt(torch.nn.functional.mse_loss(a_[i[0], i[1]].float(), b_[i[0], i[1]].float()))
    results["pseudohuber"] = pseudohuber(a_[i[0], i[1]].float(), b_[i[0], i[1]].float(), pseudohuber_threshold)
    results["modified-pseudohuber"] = modified_pseudohuber(a_[i[0], i[1]].float(),
                                                           b_[i[0], i[1]].float(),
                                                           pseudohuber_threshold)

    return results


def pseudohuber(a, b, d=1):
    """
    Returns the Pseudo-Huber loss between a and be with scaling c.
    Based on the description here: https://en.wikipedia.org/wiki/Huber_loss.
    Essentially, values < c and > c are treated with L2 and L1 losses, respectively.
    """
    residuals = a - b
    val = d ** 2 * (torch.sqrt(1 + (residuals / d) ** 2) - 1)
    return torch.mean(val)


def modified_pseudohuber(a, b, d=1):
    """
    Returns a modified Pseudo-Huber loss between a and be with scaling c.
    Based on the description here: https://en.wikipedia.org/wiki/Huber_loss.

    It has been modified so that the slope for values > c is 1, and the slope
    for values < c is < 1.

    This may prove valuable when optimizing, as it will train relatively robustly
    at the start, and then make finer-grained improvements as it surpasses the
    threshold.
    """
    residuals = a - b
    val = d * (torch.sqrt(1 + (residuals / d) ** 2) - 1)
    return torch.mean(val)


def rmsd(a, b):
    """
    Returns the RMSD between two sets of coordinates.
    """
    t = pr.calcTransformation(a, b)
    return pr.calcRMSD(t.apply(a), b)
