
# coding: utf-8

##############################################################################
#language Modeling on Penn Tree Bank
#
# This file generates new sentences sampled from the language model
#
###############################################################################

import argparse

import torch
from torch.autograd import Variable


import data_v3
import json
import pandas as pd
import preprocess
import os
from sklearn.model_selection import ShuffleSplit
import random
seed = random.seed(20180330)

# HACK for now
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
import analysis.cooccurrence_bias as cb


parser = argparse.ArgumentParser(description='PyTorch bbc Language Model')

# Model parameters.
parser.add_argument('--data', type=str, default='./data/bbc/',
                    help='location of the data corpus')
parser.add_argument('--checkpoint', type=str, default='./model.pt',
                    help='model checkpoint to use')
parser.add_argument('--outf', type=str, default='generated.txt',
                    help='output file for generated text')
parser.add_argument('--words', type=int, default='1000',
                    help='number of words to generate')
parser.add_argument('--no-sentence-reset', action='store_true',
                    help='do not reset the hidden state in between sentences')
parser.add_argument('--seed', type=int, default=1111,
                    help='random seed')
parser.add_argument('--cuda', action='store_true',
                    help='use CUDA')
parser.add_argument('--temperature', type=float, default=1.0,
                    help='temperature - higher will increase diversity')
parser.add_argument('--log-interval', type=int, default=100,
                    help='reporting interval')
args = parser.parse_args()


# Set the random seed manually for reproducibility.
torch.manual_seed(args.seed)
if torch.cuda.is_available():
    if not args.cuda:
        print("WARNING: You have a CUDA device, so you should probably run with --cuda")
    else:
        torch.cuda.manual_seed(args.seed)

if args.temperature < 1e-3:
    parser.error("--temperature has to be greater or equal 1e-3")

with open(args.checkpoint, 'rb') as f:
    model = torch.load(f)
model.eval()

if args.cuda:
    model.cuda()
else:
    model.cpu()


vocab = preprocess.read_vocab(os.path.join(args.data,'VOCAB.txt'))
idx_train = pd.read_json('idx_train.json')
idx_val = pd.read_json('idx_val.json')
idx_test = pd.read_json('idx_test.json')


corpus = data_v3.Corpus(os.path.join(args.data,'data'), vocab, idx_train, idx_train, idx_train)
ntokens = len(corpus.dictionary)
hidden = model.init_hidden(1)
input = Variable(torch.rand(1, 1).mul(ntokens).long(), volatile=True)
if args.cuda:
    input.data = input.data.cuda()

sentences = []
sent = []

with open(args.outf, 'w') as outf:
    for i in range(args.words):

        output, hidden = model(input, hidden)
        word_weights = output.squeeze().data.div(args.temperature).exp().cpu()
        word_idx = torch.multinomial(word_weights, 1)[0]
        input.data.fill_(word_idx)
        word = corpus.dictionary.idx2word[word_idx]
        sent.append(word)

        buf = word
        if (i + 1) % 20 == 0:
            buf += '\n'
        else:
            buf += ' '
        outf.write(buf)

        if word == '<eos>':
            if not args.no_sentence_reset:
                hidden = model.init_hidden(1)
            sentences.append(sent)
            sent = []

        if i % args.log_interval == 0:
            print('| Generated {}/{} words'.format(i, args.words))

if sent:
    sentences.append(sent)

# Compute bias metrics
female_cooccur, male_cooccur = cb.get_sentence_list_gender_cooccurrences(sentences)
bias, bias_norm = cb.compute_gender_cooccurrance_bias(female_cooccur, male_cooccur)
gdd = cb.compute_gender_distribution_divergence(female_cooccur, male_cooccur)

print('Gender Co-occurrence Bias: {}'.format(bias))
print('Gender Co-occurrence Bias (normalized): {}'.format(bias_norm))
print('Gender Distribution Divergence: {}'.format(gdd))
