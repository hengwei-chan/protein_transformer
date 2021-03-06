# Attention is all you need (to Predict Protein Structure)
[//]: # (Badges)
[![Build Status](https://travis-ci.com/jonathanking/protein-transformer.svg?branch=master)](https://travis-ci.com/jonathanking/protein-transformer)
[![Documentation Status](https://readthedocs.org/projects/protein-transformer/badge/?version=latest)](https://protein-transformer.readthedocs.io/en/latest/?badge=latest) 



This project explores sequence modeling techniques to predict complete (all-atom) protein structure. The work was 
inspired by language modeling methodologies, and as such incorporates Transformer and attention based models. 
Importantly, this is also a work in progress and an active research project. I welcome any thoughts or interest! 

If you'd like to look around, all code specific to this package can be found under the `protein_transformer` directory.
`train.py` loads and trains models, models are defined in `models/`, and code in `protein/`
 is responsible for manipulating and generating protein structure and sequence data. Many other research documents are
  currently included in `research/`, but are not needed to run the script.
  
 Thanks to integration with Weights and Biases, you can easily monitor the status of your model training on the Weights and Biases dashboard (below). Many training statistics are logged in realtime, including the 3D structure of each prediction.
 
 ![Weights and Biases Dashboard](/data/development/imgs/wandb_dashboard_ex.png)
  
## Installation

To run this code, it's recommended to first perform a developmental install of the package with pip in your current 
environment with `pip install -e .`. This will install the `protein_transformer` package in your environment and you 
will be free to import any classes or subroutines into your own training script if you wish.

#### Dependencies:
* ProDy
* Pytorch
* numpy
* scipy
* tqdm
* [wandb](https://docs.wandb.com)
* [PyMOL Open Source](https://pymolwiki.org/index.php/Linux_Install#Install_from_source)
* collada2gltf (`conda install -c schrodinger collada2gltf`)
## How to run

After successful installation, navigate to the `protein_transformer directory`, where you can train a model with `train.py`.

Please also modify any `wandb` initialization settings in `train.py` so that they point to your `wandb` project, and not mine :) 

This script takes many different arguments to determine different architecture and training settings. 

#### Example:
```
python train.py --data data/proteinnet/casp12.pt --name model01 -lr -0.01 -e 30 -b 12 -m conv-enc -dm 256 -l drmsd 
```

Currently supported models are based on an "Encoder Only" version of the Transformer and can be accessed with the arguments `-m {enc-only, conv-enc}`. `enc-dec` is currently deprecated.

#### Usage:
```
usage: train.py [-h] [--data DATA] [--name NAME] [-lr LEARNING_RATE]
                [-e EPOCHS] [-b BATCH_SIZE] [-es EARLY_STOPPING]
                [-nws N_WARMUP_STEPS] [-cg CLIP]
                [-l {mse,drmsd,lndrmsd,combined}] [--train_only]
                [--lr_scheduling {noam,plateau}] [--patience PATIENCE]
                [--early_stopping_threshold EARLY_STOPPING_THRESHOLD]
                [-esm {train-mse,test-mse,valid-10-mse,valid-20-mse,valid-30-mse,valid-40-mse,valid-50-mse,valid-70-mse,valid-90-mse,train-drmsd,test-drmsd,valid-10-drmsd,valid-20-drmsd,valid-30-drmsd,valid-40-drmsd,valid-50-drmsd,valid-70-drmsd,valid-90-drmsd,train-lndrmsd,test-lndrmsd,valid-10-lndrmsd,valid-20-lndrmsd,valid-30-lndrmsd,valid-40-lndrmsd,valid-50-lndrmsd,valid-70-lndrmsd,valid-90-lndrmsd,train-combined,test-combined,valid-10-combined,valid-20-combined,valid-30-combined,valid-40-combined,valid-50-combined,valid-70-combined,valid-90-combined}]
                [--without_angle_means] [--eval_train EVAL_TRAIN]
                [-opt {adam,sgd}] [-fctf FRACTION_COMPLETE_TF]
                [-fsstf FRACTION_SUBSEQ_TF]
                [--skip_missing_res_train SKIP_MISSING_RES_TRAIN]
                [--repeat_train REPEAT_TRAIN] [-s SEED]
                [--combined_drmsd_weight COMBINED_DRMSD_WEIGHT]
                [--batching_order {descending,ascending,binned-random}]
                [--backbone_loss] [--sequential_drmsd_loss] [--bins BINS]
                [--train_eval_downsample TRAIN_EVAL_DOWNSAMPLE]
                [--automatically_determine_batch_size AUTOMATICALLY_DETERMINE_BATCH_SIZE]
                [-m MODEL] [-dm D_MODEL] [-dih D_INNER_HID] [-nh N_HEAD]
                [-nl N_LAYERS] [-do DROPOUT] [--postnorm]
                [--weight_decay WEIGHT_DECAY] [--conv1_size CONV1_SIZE]
                [--conv2_size CONV2_SIZE] [--conv3_size CONV3_SIZE]
                [--conv1_reduc CONV1_REDUC] [--conv2_reduc CONV2_REDUC]
                [--conv3_reduc CONV3_REDUC] [--use_embedding USE_EMBEDDING]
                [--conv_out_matches_dm CONV_OUT_MATCHES_DM]
                [--log_structure_step LOG_STRUCTURE_STEP]
                [--log_val_struct_step LOG_VAL_STRUCT_STEP]
                [--log_wandb_step LOG_WANDB_STEP] [--save_pngs SAVE_PNGS]
                [--no_cuda] [-c CLUSTER] [--restart] [--restart_opt]
                [--checkpoint_time_interval CHECKPOINT_TIME_INTERVAL]
                [--load_chkpt LOAD_CHKPT]

optional arguments:
  -h, --help            show this help message and exit

Required Args:
  --data DATA           Path to training data.
  --name NAME           The model name.

Training Args:
  -lr LEARNING_RATE, --learning_rate LEARNING_RATE
  -e EPOCHS, --epochs EPOCHS
  -b BATCH_SIZE, --batch_size BATCH_SIZE
  -es EARLY_STOPPING, --early_stopping EARLY_STOPPING
                        Stops if training hasn't improved in X epochs
  -nws N_WARMUP_STEPS, --n_warmup_steps N_WARMUP_STEPS
                        Number of warmup training steps when using lr-
                        scheduling as proposed in the originalTransformer
                        paper.
  -cg CLIP, --clip CLIP
                        Gradient clipping value.
  -l {mse,drmsd,lndrmsd,combined}, --loss {mse,drmsd,lndrmsd,combined}
                        Loss used to train the model. Can be root mean squared
                        error (RMSE), distance-based root mean squared
                        distance (DRMSD), length-normalized DRMSD (ln-DRMSD)
                        or a combination of RMSE and ln-DRMSD.
  --train_only          Train, validation, and testing sets are the same. Only
                        report train accuracy.
  --lr_scheduling {noam,plateau}
                        noam: Use learning rate scheduling as described in
                        Transformer paper, plateau: Decrease learning rate
                        after Validation loss plateaus.
  --patience PATIENCE   Number of epochs to wait before reducing LR for
                        plateau scheduler.
  --early_stopping_threshold EARLY_STOPPING_THRESHOLD
                        Threshold for considering improvements during
                        training/lr scheduling.
  -esm {train-mse,test-mse,valid-10-mse,valid-20-mse,valid-30-mse,valid-40-mse,valid-50-mse,valid-70-mse,valid-90-mse,train-drmsd,test-drmsd,valid-10-drmsd,valid-20-drmsd,valid-30-drmsd,valid-40-drmsd,valid-50-drmsd,valid-70-drmsd,valid-90-drmsd,train-lndrmsd,test-lndrmsd,valid-10-lndrmsd,valid-20-lndrmsd,valid-30-lndrmsd,valid-40-lndrmsd,valid-50-lndrmsd,valid-70-lndrmsd,valid-90-lndrmsd,train-combined,test-combined,valid-10-combined,valid-20-combined,valid-30-combined,valid-40-combined,valid-50-combined,valid-70-combined,valid-90-combined}, --early_stopping_metric {train-mse,test-mse,valid-10-mse,valid-20-mse,valid-30-mse,valid-40-mse,valid-50-mse,valid-70-mse,valid-90-mse,train-drmsd,test-drmsd,valid-10-drmsd,valid-20-drmsd,valid-30-drmsd,valid-40-drmsd,valid-50-drmsd,valid-70-drmsd,valid-90-drmsd,train-lndrmsd,test-lndrmsd,valid-10-lndrmsd,valid-20-lndrmsd,valid-30-lndrmsd,valid-40-lndrmsd,valid-50-lndrmsd,valid-70-lndrmsd,valid-90-lndrmsd,train-combined,test-combined,valid-10-combined,valid-20-combined,valid-30-combined,valid-40-combined,valid-50-combined,valid-70-combined,valid-90-combined}
                        Metric observed for early stopping and LR scheduling.
  --without_angle_means
                        Do not initialize the model with pre-computed angle
                        means.
  --eval_train EVAL_TRAIN
                        Perform an evaluation of the entire training set after
                        a training epoch.
  -opt {adam,sgd}, --optimizer {adam,sgd}
                        Training optimizer.
  -fctf FRACTION_COMPLETE_TF, --fraction_complete_tf FRACTION_COMPLETE_TF
                        Fraction of the time to use teacher forcing for every
                        timestep of the batch. Model trains fastest when this
                        is 1.
  -fsstf FRACTION_SUBSEQ_TF, --fraction_subseq_tf FRACTION_SUBSEQ_TF
                        Fraction of the time to use teacher forcing on a per-
                        timestep basis.
  --skip_missing_res_train SKIP_MISSING_RES_TRAIN
                        When training, skip over batches that have missing
                        residues. This can make trainingfaster if using
                        teacher forcing.
  --repeat_train REPEAT_TRAIN
                        Duplicate the training set X times. Useful for
                        training on small datasets.
  -s SEED, --seed SEED  The random number generator seed for numpy and torch.
  --combined_drmsd_weight COMBINED_DRMSD_WEIGHT
                        When combining losses, use weight w for loss = w *
                        drmsd + (1-w) * mse.
  --batching_order {descending,ascending,binned-random}
                        Method for constructuing minibatches of proteins
                        w.r.t. sequence length. Batches can be provided in
                        descending/ascending order, or 'binned-random' which
                        keeps the sequencesin a batch similar, while
                        randomizing the bins/batches.
  --backbone_loss       While training, only evaluate loss on the backbone.
  --sequential_drmsd_loss
                        Compute DRMSD loss without batch-level
                        parallelization.
  --bins BINS           Number of bins for protein dataset batching.
  --train_eval_downsample TRAIN_EVAL_DOWNSAMPLE
                        Fraction of training set to evaluate on each epoch.
  --automatically_determine_batch_size AUTOMATICALLY_DETERMINE_BATCH_SIZE, -adbs AUTOMATICALLY_DETERMINE_BATCH_SIZE
                        Experimentally determinethe maximum allowable
                        batchsize for training.

Model Args:
  -m MODEL, --model MODEL
                        Model architecture type. Encoder only or
                        encoder/decoder model.
  -dm D_MODEL, --d_model D_MODEL
                        Dimension of each sequence item in the model. Each
                        layer uses the same dimension for simplicity.
  -dih D_INNER_HID, --d_inner_hid D_INNER_HID
                        Dimmension of the inner layer of the feed-forward
                        layer at the end of every Transformer block.
  -nh N_HEAD, --n_head N_HEAD
                        Number of attention heads.
  -nl N_LAYERS, --n_layers N_LAYERS
                        Number of layers in the model. If using
                        encoder/decoder model, the encoder and decoder both
                        have this number of layers.
  -do DROPOUT, --dropout DROPOUT
                        Dropout applied between layers.
  --postnorm            Use post-layer normalization, as depicted in the
                        original figure for the Transformer model. May not
                        train as well as pre-layer normalization.
  --weight_decay WEIGHT_DECAY
                        Applies weight decay to model weights.
  --conv1_size CONV1_SIZE
                        Size of conv1 layer kernel for 'conv-enc' model.
  --conv2_size CONV2_SIZE
                        Size of conv2 layer kernel for 'conv-enc' model.
  --conv3_size CONV3_SIZE
                        Size of conv2 layer kernel for 'conv-enc' model.
  --conv1_reduc CONV1_REDUC
                        Factor by which conv1 layer reduces the number of
                        channels for 'conv-enc' model.
  --conv2_reduc CONV2_REDUC
                        Factor by which conv2 layer reduces the number of
                        channels for 'conv-enc' model.
  --conv3_reduc CONV3_REDUC
                        Factor by which conv2 layer reduces the number of
                        channels for 'conv-enc' model.
  --use_embedding USE_EMBEDDING
                        Whether or not to use embedding layer in the
                        transformer model.
  --conv_out_matches_dm CONV_OUT_MATCHES_DM
                        If True, the final convolution layer at the start of
                        the model will match the dimensionality of the
                        requested d_model. Used for ConvEnc models.

Saving Args:
  --log_structure_step LOG_STRUCTURE_STEP
                        Frequency of logging structure data during training.
  --log_val_struct_step LOG_VAL_STRUCT_STEP, -lvs LOG_VAL_STRUCT_STEP
                        During training, make predictions on 1 structure from
                        every validation set.
  --log_wandb_step LOG_WANDB_STEP
                        Frequency of logging to wandb during training.
  --save_pngs SAVE_PNGS, -png SAVE_PNGS
                        Save images when making structures.
  --no_cuda
  -c CLUSTER, --cluster CLUSTER
                        Set of parameters to facilitate training on a remote
                        cluster. Limited I/O, etc.
  --restart             Does not resume training.
  --restart_opt         Resumes training but does not load the optimizer
                        state.
  --checkpoint_time_interval CHECKPOINT_TIME_INTERVAL
                        The amount of time (in hours) after which a model
                        checkpoint is made, regardless of its performance.
  --load_chkpt LOAD_CHKPT
                        Path from which to load a model checkpoint.

```

## Training Data

The training data is based on Mohammed AlQuraishi's [ProteinNet](https://github.com/aqlaboratory/proteinnet). Preprocessed  data from the CASP12 competition that has been modified to work with this project can be downloaded [here](https://pitt.box.com/s/gcaxsjbdhjp4zsyjzqbvum8795w8vay5) (~3GB, a 30% thinning of the dataset). 

My data uses the same train/test/validation sets as ProteinNet. While, like ProteinNet, it includes protein sequences and coordinates, I have modified it to include information about the entire protein structure (both backbone and sidechain atoms). Thus, each protein in the dataset includes information for sequence, interior torsional/bond angles, and coordinates. It does not include multiple sequence alignments or secondary structure annotation.

The data is saved with PyTorch and stored in a Python dictionary like so:
```python
data = {"train": {"seq": [seq1, seq2, ...],
                  "ang": [ang1, ang2, ...],
                  "crd": [crd1, crd2, ...],
                  "ids": [id1, id2, ...]
                  },
        "valid-30": {...},
            ...
        "valid-90": {...},
        "test": {...},
        "settings": {...}
        }
```

## Other information
Please visit my [Project Notes](docs/ProjectNotes.md) for more project details.


### Acknowledgements

This repository was originally a fork from [https://github.com/jadore801120/attention-is-all-you-need-pytorch](https://github.com/jadore801120/attention-is-all-you-need-pytorch), but since then has been extensively rewritten to match the needs of this specific project as I have become more comfortable with Pytorch, Transformers, and the like. Many thanks for [jadore801120](https://github.com/jadore801120/) for the framework.

I, Jonathan King, am a predoctoral trainee supported by NIH T32 training grant T32 EB009403 as part of the HHMI-NIBIB Interfaces Initiative.
 
Project structure (continuous integration, docs, testing) based on the 
[Computational Molecular Science Python Cookiecutter](https://github.com/molssi/cookiecutter-cms) version 1.1.

### Copyright

Copyright (c) 2020, Jonathan King
