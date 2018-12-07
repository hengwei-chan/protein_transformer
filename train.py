'''
This script handling the training process.
'''

import argparse
import math
import time

from tqdm import tqdm
import torch
import torch.nn.functional as F
import torch.optim as optim
import torch.utils.data
import transformer.Constants as Constants
from dataset import paired_collate_fn, ProteinDataset
from transformer.Models import Transformer
from transformer.Optim import ScheduledOptim
from transformer.Structure import angles2coords, drmsd
from torch import multiprocessing

def cal_performance(pred, gold, device):
    ''' Apply label smoothing if needed '''
    # TODO: possibly add more info for recording performance
    loss = cal_loss(pred, gold, device)

    # pred = pred.max(1)[1]
    # gold = gold.contiguous().view(-1)
    # non_pad_mask = gold.ne(Constants.PAD)

    return loss


def unpad_angle_vectors(pred, gold, device):
    not_padded_mask = (gold != 0).any(dim=-1)
    not_padded_mask = not_padded_mask.view(-1, 1).repeat(1, 1, 11).view(gold.shape[0], -1, gold.shape[-1])  # Repeat along last dim
    if device.type == "cuda":
        pred_unpadded = pred.cuda() * not_padded_mask.type(torch.cuda.FloatTensor)
        gold_unpadded = gold.cuda() * not_padded_mask.type(torch.cuda.FloatTensor)
    else:
        pred_unpadded = pred * not_padded_mask.type(torch.FloatTensor)
        gold_unpadded = gold * not_padded_mask.type(torch.FloatTensor)
    return pred_unpadded, gold_unpadded


def cal_loss(pred, gold, device):
    ''' Calculate DRMSD loss. '''
    device = torch.device("cpu")
    pred, gold = pred.to(device), gold.to(device)
    pred_unpadded, gold_unpadded = unpad_angle_vectors(pred, gold, device)

    losses = []
    for pred_item, gold_item in zip(pred_unpadded, gold_unpadded):
        true_coords = angles2coords(gold_item, device)
        pred_coords = angles2coords(pred_item, device)
        loss = drmsd(pred_coords, true_coords)
        losses.append(loss)

    return torch.mean(torch.stack(losses))


def train_epoch(model, training_data, optimizer, device):
    ''' Epoch operation in training phase'''

    model.train()

    total_loss = 0
    n_batches = 0.0

    for batch in tqdm(
            training_data, mininterval=2,
            desc='  - (Training)   ', leave=False):

        # prepare data
        src_seq, src_pos, tgt_seq, tgt_pos = map(lambda x: x.to(device), batch)
        gold = tgt_seq[:, 1:]

        # forward
        optimizer.zero_grad()
        pred = model(src_seq, src_pos, tgt_seq, tgt_pos)

        # backward
        loss = cal_performance(pred, gold, device)
        loss.backward()

        # update parameters
        # optimizer.step_and_update_lr()
        optimizer.step()

        # note keeping
        total_loss += loss.item()
        n_batches += 1

    return total_loss / n_batches

def eval_epoch(model, validation_data, device):
    ''' Epoch operation in evaluation phase '''

    model.eval()

    total_loss = 0
    n_batches = 0.0


    with torch.no_grad():
        for batch in tqdm(
                validation_data, mininterval=2,
                desc='  - (Validation) ', leave=False):

            # prepare data
            src_seq, src_pos, tgt_seq, tgt_pos = map(lambda x: x.to(device), batch)
            gold = tgt_seq[:, 1:]

            # forward
            pred = model(src_seq, src_pos, tgt_seq, tgt_pos)
            loss = cal_performance(pred, gold, device)

            # note keeping
            total_loss += loss.item()
            n_batches += 1

    return total_loss / n_batches

def train(model, training_data, validation_data, optimizer, device, opt):
    ''' Start training '''

    log_train_file = None
    log_valid_file = None

    # Set up training/validation log files.
    if opt.log:
        log_train_file = opt.log + '.train.log'
        log_valid_file = opt.log + '.valid.log'

        print('[Info] Training performance will be written to file: {} and {}'.format(
            log_train_file, log_valid_file))

        with open(log_train_file, 'w') as log_tf, open(log_valid_file, 'w') as log_vf:
            log_tf.write('epoch,loss,ppl,accuracy\n')
            log_vf.write('epoch,loss,ppl,accuracy\n')

    valid_losses = []
    epoch_last_improved = -1
    best_valid_loss_so_far = 10000
    for epoch_i in range(opt.epoch):
        print('[ Epoch', epoch_i, ']')

        start = time.time()
        train_loss = train_epoch(
            model, training_data, optimizer, device)
        print('  - (Training)   loss: {loss: 8.5f} '\
              'elapse: {elapse:3.3f} min'.format(
                  loss=train_loss,
                  elapse=(time.time()-start)/60))

        start = time.time()
        valid_loss = eval_epoch(model, validation_data, device)
        print('  - (Validation) loss: {loss: 8.5f}, '\
                'elapse: {elapse:3.3f} min'.format(
                    loss=valid_loss,
                    elapse=(time.time()-start)/60))

        valid_losses.append(valid_loss)

        if valid_loss < best_valid_loss_so_far:
            best_valid_loss_so_far = valid_loss
            epoch_last_improved = epoch_i
        elif epoch_i - epoch_last_improved > 100:
            # Model hasn't improved in 100 epochs
            print("No improvement for 100 epochs. Stopping model training early.")
            break


        # Record model state and log training info
        model_state_dict = model.state_dict()
        checkpoint = {
            'model': model_state_dict,
            'settings': opt,
            'epoch': epoch_i}

        if opt.save_model:
            if opt.save_mode == 'all':
                model_name = opt.save_model + '_loss_{vloss:3.3f}.chkpt'.format(vloss=valid_loss)
                torch.save(checkpoint, model_name)
            elif opt.save_mode == 'best':
                model_name = opt.save_model + '.chkpt'
                if valid_loss <= min(valid_losses):
                    torch.save(checkpoint, model_name)
                    print('    - [Info] The checkpoint file has been updated.')

        if log_train_file and log_valid_file:
            with open(log_train_file, 'a') as log_tf, open(log_valid_file, 'a') as log_vf:
                log_tf.write('{epoch},{loss: 8.5f},{ppl: 8.5f}\n'.format(
                    epoch=epoch_i, loss=train_loss,
                    ppl=math.exp(min(train_loss, 100))))
                log_vf.write('{epoch},{loss: 8.5f},{ppl: 8.5f}\n'.format(
                    epoch=epoch_i, loss=valid_loss,
                    ppl=math.exp(min(valid_loss, 100))))

def main():
    ''' Main function '''
    parser = argparse.ArgumentParser()

    parser.add_argument('-data', required=True)

    parser.add_argument('-epoch', type=int, default=10)
    parser.add_argument('-batch_size', type=int, default=64)

    parser.add_argument('-d_word_vec', type=int, default=20)
    parser.add_argument('-d_model', type=int, default=512)
    parser.add_argument('-d_inner_hid', type=int, default=2048)
    parser.add_argument('-d_k', type=int, default=64)
    parser.add_argument('-d_v', type=int, default=64)

    parser.add_argument('-n_head', type=int, default=8)
    parser.add_argument('-n_layers', type=int, default=6)
    parser.add_argument('-n_warmup_steps', type=int, default=4000)

    parser.add_argument('-dropout', type=float, default=0.1)

    parser.add_argument('-log', default=None)
    parser.add_argument('-save_model', default=None)
    parser.add_argument('-save_mode', type=str, choices=['all', 'best'], default='best')

    parser.add_argument('-no_cuda', action='store_true')
    parser.add_argument('-label_smoothing', action='store_true')

    opt = parser.parse_args()
    opt.cuda = not opt.no_cuda
    opt.d_word_vec = opt.d_model

    #========= Loading Dataset =========#
    data = torch.load(opt.data)
    opt.max_token_seq_len = data['settings']["max_len"]

    training_data, validation_data = prepare_dataloaders(data, opt)

    #========= Preparing Model =========#

    print(opt)

    device = torch.device('cuda' if opt.cuda else 'cpu')
    transformer = Transformer(
        opt.max_token_seq_len,
        d_k=opt.d_k,
        d_v=opt.d_v,
        d_model=opt.d_model,
        d_inner=opt.d_inner_hid,
        n_layers=opt.n_layers,
        n_head=opt.n_head,
        dropout=opt.dropout).to(device)

    # optimizer = ScheduledOptim(
    #     optim.Adam(
    #         filter(lambda x: x.requires_grad, transformer.parameters()),
    #         betas=(0.9, 0.98), eps=1e-09),
    #     opt.d_model, opt.n_warmup_steps)

    optimizer =  optim.Adam(filter(lambda x: x.requires_grad, transformer.parameters()),
                            betas=(0.9, 0.98), eps=1e-09, lr=0.0001)

    train(transformer, training_data, validation_data, optimizer, device ,opt)

def prepare_dataloaders(data, opt):
    """ data is a dictionary containing all necessary training data."""
    # ========= Preparing DataLoader =========#
    # TODO create "data.pkl" file which is a dictionary with the necessary data
    train_loader = torch.utils.data.DataLoader(
        ProteinDataset(
            seqs=data['train']['seq'],
            angs=data['train']['ang']),
        num_workers=2,
        batch_size=opt.batch_size,
        collate_fn=paired_collate_fn,
        shuffle=True)

    valid_loader = torch.utils.data.DataLoader(
        ProteinDataset(
            seqs=data['valid']['seq'],
            angs=data['valid']['ang']),
        num_workers=2,
        batch_size=opt.batch_size,
        collate_fn=paired_collate_fn)
    return train_loader, valid_loader


if __name__ == '__main__':
    main()
