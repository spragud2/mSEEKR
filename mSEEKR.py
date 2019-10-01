import corefunctions
import argparse
from itertools import product
import numpy as np
from seekr.fasta_reader import Reader
from collections import defaultdict
from multiprocessing import pool
import sys
import os
import pickle
from math import log
import pandas as pd
from operator import itemgetter

''' hmmCalc
Run several functions including viterbi algorithm, log-likelihood, and generate output dataframes
Input: fasta file information
Output: dataframe object
'''
def hmmCalc(data):
    tHead,tSeq = data
    O,oIdx,nBP = corefunctions.kmersWithAmbigIndex(tSeq,k)
    A,E,states,pi= hmm['A'],hmm['E'],hmm['states'],hmm['pi']
    bTrack = corefunctions.viterbi(O,A,E,states,pi)
    #Zip the indices of unambig k-mers with their viterbi derived HMM state labels
    coordBTrack = list(zip(oIdx,bTrack)) # [(1,'-'),(2,'+',...(n,'+'))]
    mergedTrack = coordBTrack + nBP # add back in ambig locations
    mergedTrack.sort(key=itemgetter(0)) # sort master list by index
    hmmTrack = [i[1] for i in mergedTrack] # fetch just state label from mergedTrack ['-','+',...,'+']
    groupedHits = corefunctions.groupHMM(hmmTrack) # ['-----','++++++++++','-','++++','------------']

    # Return sequences of HMM hits, and their start and end locations in the original sequence
    seqHits,starts,ends = corefunctions.formatHits(groupedHits,k,tSeq)

    fwdPs = corefunctions.getFwd(seqHits,A,pi,states,E,k,alphabet)
    if (seqHits) and (not args.wt):
        df = corefunctions.hitOutput(seqHits,starts,ends,k,E,fwdPs,tHead,tSeq)
        return tHead,df

    # Alternative output (transcript by transcript)
    elif (seqHits) and (args.wt):
        df = corefunctions.transcriptOutput(seqHits,starts,ends,k,E,fwdPs,tHead,tSeq)
        return tHead,df
    else:
        return tHead,None


parser = argparse.ArgumentParser()
parser.add_argument("--model",type=str,help='Path to directory containing hmm models from train.py')
parser.add_argument("-k",type=str,help='Comma delimited string, values of k to use')
parser.add_argument('--db',type=str,help='Path to fasta file with sequences to calculate similarity score')
parser.add_argument('--prefix',type=str,help='String, Output file prefix;default=None')
#parser.add_argument('--bkg',type=str,help='Path to fasta file from which to calculate background nucleotide frequencies, if not passed default is uniform',default=None)
parser.add_argument('-a',type=str,help='String, Alphabet to generate k-mers (e.g. ATCG); default=ATCG',default='ATCG')
parser.add_argument('-n',type=int,help='Integer 1 <= n <= max(cores), Number of processor cores to use; default = 1. This scales with the number of sequence comparisons in --db',default=1)
parser.add_argument('--fasta',action='store_true',help='FLAG: print sequence of hit, ignored if --wt is passed')
parser.add_argument('--wt',action='store_true',help='FLAG: If passed, return total log-likelihood over all hits in a fasta entry')
args = parser.parse_args()
alphabet = [letter for letter in args.a]
#Loop over values of k
kVals = args.k.split(',')
args.a = args.a.upper()
model = args.model

if not model.endswith('/'):
    model +='/'
for kVal in kVals:
    kDir = model+kVal+'/'
    modelName = model.split('/')[-2]
    # Check if file exists and open if so, else skip this iteration of the loop
    try:
        hmm = pickle.load(open(kDir+'hmm.mkv','rb'))
    except:
        print(f'Value of k={kVal} not found, skipping...')
        continue
    # Explicitly determine k from the size of the log matrix and the size of the alphabet used to generate it
    k = int(log(len(hmm['E']['+'].keys()),len(args.a)))
    kmers = [''.join(p) for p in product(alphabet,repeat=k)] # generate k-mers
    target = Reader(args.db)
    targetSeqs,targetHeaders = target.get_seqs(),target.get_headers()
    targetMap = defaultdict(list)
    #Pool processes onto number of CPU cores specified by the user
    with pool.Pool(args.n) as multiN:
        jobs = multiN.starmap(hmmCalc,product(*[list(zip(targetHeaders,targetSeqs))]))
        dataDict = dict(jobs)
    #Check if no hits were found
    # if not all(v == None for v in dataDict.values()):
    if not args.wt:
        dataFrames = pd.concat([df for df in dataDict.values() if not None])
        dataFrames['Length'] = dataFrames['End'] - dataFrames['Start']
        dataFrames = dataFrames[['Start','End','Length','fwdLLR','kmerLLR','seqName','Sequence']]
        if not args.fasta:
            dataFrames = dataFrames[['Start','End','Length','fwdLLR','kmerLLR','seqName']]
        dataFrames.sort_values(by='fwdLLR',ascending=False,inplace=True)
        dataFrames.reset_index(inplace=True,drop=True)
        dataFrames.to_csv(f'./{args.prefix}_{modelName}_{k}.txt',sep='\t')
    elif args.wt:
        dataFrames = pd.concat([df for df in dataDict.values() if not None])
        dataFrames = dataFrames[['seqName','sumFwdLLR','sumLLR','totalLenHits','fracTranscriptHit','longestHit']]
        dataFrames.sort_values(by='sumFwdLLR',ascending=False,inplace=True)
        dataFrames.reset_index(inplace=True,drop=True)
        dataFrames.to_csv(f'./{args.prefix}_{modelName}_{k}.txt',sep='\t')
