import numpy as np
from itertools import product
from itertools import groupby
from scipy.special import logsumexp
import pandas as pd


''' Key for itertools groupby
    Alters flag when sequence changes from one condition to another
    Input: Sequence of characters with some alphabet and a trigger condition
    Output: flag: 0 or 1
'''

class Key(object):
    def __init__(self):
        self.is_nt,self.flag,self.prev = ['-','N'],[0,1],None
    def __call__(self,e):
        # Initial True/False  if first char in string is + or -
        ebool = any(x in self.is_nt for x in e)
        # If key exists (self.prev is defined), do true/false check
        # else, set value to false
        if self.prev:
            prevbool = any(x in self.is_nt for x in self.prev)
        else:
            prevbool = None
        # if string goes from - to +, or + to -, swap flag
        if prevbool != ebool:
            self.flag = self.flag[::-1]
        # set previous encountered char, for the next interation of this, to the current value
        self.prev = e
        return self.flag[0]

''' groupHMM
Return a list of strings separating HMM state labels
Input: String
Output: List of lists
Output example: ['---','++','------','+','-------',...]
'''
def groupHMM(seq):
    return [''.join(list(g)) for k,g in groupby(seq,key=Key())]

''' kmersWithAmbigIndex
Return list of kmers, indices of k-mers without ambiguity, and indices of those
with ambiguity
Input: string
Output: List of string, list of indices, list of indices
'''

def hitOutput(seqHits,starts,ends,k,E,tHead,tSeq):
    info = list(zip(seqHits,starts,ends))
    dataDict = dict(zip(list(range(len(seqHits))),info))
    df = pd.DataFrame.from_dict(dataDict,orient='index')
    #calculate log-likelihood ratio of k-mers in the + model vs - model
    df['kmerLLR'] = LLR(seqHits,k,E)
    df['seqName'] = tHead
    df.columns = ['Sequence','Start','End','kmerLLR','seqName']
    df.sort_values(by='kmerLLR',inplace=True,ascending=False)
    df.reset_index(inplace=True)
    fa = df['Sequence']
    df = df[['Start','End','kmerLLR','seqName','Sequence']]

    return df

def transcriptOutput(seqHits,starts,ends,k,E,tHead,tSeq):

    sumHits = LLR(seqHits,k,E)
    lens = ends-starts # lengths of individual hits
    df = pd.DataFrame([np.sum(sumHits)]) # sum of hits
    df['totalLenHits'] = (np.sum(lens)) # sum of all hit lengths
    df['fracTranscriptHit'] = df['totalLenHits']/len(tSeq) # fraction of transcript that is hit
    df['longestHit'] = np.max(lens) # longest HMM hit
    df['seqName'] = tHead
    df.columns = ['sumLLR','totalLenHits','fracTranscriptHit','longestHit','seqName']

    return df
def kmersWithAmbigIndex(tSeq,k):
    O = [tSeq[i:i+k].upper() for i in range(0,len(tSeq)-k+1)]
    O = [o for o in O if 'N' not in o]
    # Match k-mers without ambig char to index in original string
    oIdx = [i for i in range(0,len(tSeq)-k+1) if 'N' not in tSeq[i:i+k]]
    # Match k-mers with ambig char to index in original string
    nBP = [i for i in range(0,len(tSeq)-k+1) if 'N' in tSeq[i:i+k]]
    # zip the indices with marker character N
    nBP = list(zip(nBP,['N']*len(nBP)))
    return O, oIdx, nBP

''' LLR
Return log-likelihood ratio between two models in HMM for + k-mers
Input: sequnce of hits, value of k, k-mer frequencies in HMM emmission matrix
Output: Array of LLRs for each hit
'''

def LLR(hits,k,E):
    arr = np.zeros(len(hits))
    for i,hit in enumerate(hits):
        LLRPos,LLRNeg=0,0
        for j in range(len(hit)-k+1):
            kmer=hit[j:j+k]
            LLRPos += E['+'][kmer]
            LLRNeg += E['-'][kmer]
        llr = LLRPos-LLRNeg
        arr[i] = llr
    return arr

def getFwd(seqHits,A,pi,states,E,k,alphabet):
    fwdPs = []
    for hit in seqHits:
        O = [hit[i:i+k].upper() for i in range(0,len(hit)-k+1)]
        O = [o for o in O if 'N' not in o]
        '''
        forward algorithm to calculate log P(O|HMM)
        '''
        fP = fwd(O,A,pi,states,E,k,alphabet)
        fwdPs.append(fP)
    return fwdPs

def formatHits(groupedHits,k,tSeq):
    idx = 0
    indexGroupHits = []
    # Loop below formats the hmm output as such:
    # [([0,1,2]),'---'),([3,4],'++'),([5],'-'),...]
    # Grouping HMM states with their correct index in the list of k-mers
    for i,group in enumerate(groupedHits):
        indexGroupHits.append([])
        for kmer in group:
            indexGroupHits[i].append(idx)
            idx+=1
    hits = list(zip(indexGroupHits,groupedHits))
    seqHits = []
    seqHitCoords = []
    for group in hits:
        if '+' in group[1]:
            start,end = group[0][0],group[0][-1]+k #convert k-mer coord to bp coord
            seqHitCoords.append(f'{start}:{end}')
            seqHits.append(tSeq[start:end])
    starts = np.array([int(c.split(':')[0]) for c in seqHitCoords])
    ends = np.array([int(c.split(':')[1]) for c in seqHitCoords])
    return seqHits,starts,ends

def transitionMatrix(kmers,k,alphabet):
    states = np.zeros((4**(int(k)-1), 4), dtype=np.float64)
    stateKmers = [''.join(p) for p in product(alphabet,repeat=k-1)]
    for i, currState in enumerate(stateKmers):
        tot = 0
        for j, nextState in enumerate(alphabet):
            count = kmers[currState+nextState]
            tot += count
        if tot > 0:
            for j, nextState in enumerate(alphabet):
                states[i, j] = kmers[currState+nextState] / float(tot)
    return states

# calculate nucleotide content of a sequence... unused now
def nucContent(nullSeqs,alphabet):
    seqs = ''.join(nullSeqs)
    seqs = seqs.upper()
    freq = [seqs.count(nt)/len(seqs) for nt in alphabet]
    return dict(zip(alphabet,freq))

# Calculate the log2 odds table between two matrices
def logLTbl(q,null):
    return np.log2(q) - np.log2(null)

'''
HMM: Generate dictionaries containing information necessary to perform the viterbi algorithm

Inputs: qCounts - query count dictionary
        nCounts - null count dictionary
        k - value of k
        alphabet - alphabet (ATCG)
        m: + to + transition probability
        n: - to - transition probability
Returns:    A - Dictionary, Hidden state transition matrix
            E - Dictionary, Emission matrix, kmer counts
            state - tuple, list of states (+,-)
            pi - Dictionary, initial probability of being in + or -


'''

def HMM(qCounts,nCounts,k,alphabet,m,n):
    kmers = [''.join(p) for p in product(alphabet,repeat=k)]
    hmmDict = {}
    countArr = np.array(list(qCounts.values()))
    # Convert raw counts to frequencies, then log probability
    hmmDict['+'] = np.log2(countArr/np.sum(countArr))
    #hmmDict['+'] = hmmDict['+'] - np.mean(hmmDict['+'])
    countArr = np.array(list(nCounts.values()))
    # Convert raw counts to frequencies, then log probability
    hmmDict['-'] = np.log2(countArr/np.sum(countArr))
    #hmmDict['-'] = hmmDict['-'] - np.mean(hmmDict['-'])

    states = ('+','-')
    pi = {'+':np.log2(.5),'-':np.log2(.5)}
    A = {'+':{'+':np.log2(m),'-':np.log2(1-m)},'-':{'+':np.log2(1-n),'-':np.log2(n)}}
    E = {'+': dict(zip(kmers,hmmDict['+'])),'-':dict(zip(kmers,hmmDict['-']))}
    return A,E,states,pi


'''
Viterbi: Calculate the most likely sequence of hidden states given observed sequence, transition matrix, and emission matrix

Inputs: O - list, observed sequence of k-mers
        A - dictionary, transition matrices of hidden states
        E - dictionary, emission matrices of hidden states
        states - list, hidden states (+,-)
        m: + to + transition probability
        n: - to - transition probability
        pi - Dictionary, initial probability of being in + or -
Returns:    backTrack - list, sequence of hidden states


'''
def viterbi(O,A,E,states,pi):

    # Initialize list of dictionaries for the current step
    # and ukprev, which tracks the state transitions that maximize the 'viterbi function'
    uk=[{}]
    ukprev = [{}]
    N = len(O)
    # calculate initial probabilities in each state given the first kmer
    for state in states:
        uk[0][state]=pi[state]+E[state][O[0]]
        ukprev[0][state] = None # previous state does not exist, set to None
    # Loop through observed sequence
    # For each state, calculate the cumulative probability recursively
    # Store the state transition that maximizes this probability in ukprev for each current state
    for n in range(1,N):
        uk.append({})
        ukprev.append({})
        for state in states:
            prevSelState = states[0] # this is just an arbitrary choice to start checking at the start of the list
            currMaxProb = A[state][prevSelState] + uk[n-1][prevSelState] # probability function
            for pState in states[1:]: # now check the other states...
                currProb = A[state][pState] + uk[n-1][pState]
                if currProb > currMaxProb: # if larger then the first one we checked, we have a new winner, store and continue loop and repeat
                    currMaxProb = currProb
                    prevSelState = pState
            # The emission probability is constant so add at the end rather than in the loop
            max_prob = currMaxProb + E[state][O[n]]
            # save the cumalitive probability for each state
            uk[n][state] = max_prob
            # save the previous state that maximized this probability above
            ukprev[n][state] = prevSelState

    z = max(uk[-1],key=uk[-n].get) # retrieve the state associated with largest log probability
    prev = ukprev[-1][z] # get the state BEFORE "z" above that maximized z
    backtrack = [z,prev] # start our backtrack with knowns
    # Loop through BACKWARDS, getting the previous state that yielded the 'current' max state
    for n in range(N-2,-1,-1):
        backtrack.append(ukprev[n+1][prev]) # n+1 is the "current" state as we're going backwards, ukprev[n+1][prev] returns the state that maximized
        prev = ukprev[n+1][prev]
    backtrack = backtrack[::-1] # reverse the order
    return backtrack

'''
The forward algorithm calculates the probability of being in state i at time t, given all observations from time 1 to t. 

The forward algorithm is essentially identical to the Viterbi algorithm, with the major difference being that 
at each time step, we sum up all probabilities rather than choosing the maximizing transition.

The forward algorithm is also crucial for calculatating the likelihood of the observation given the entire model, i.e.

P(Observed Sequence | Model) = sum probabilities at the end point (last observation) over all states, yielding the total probability
of the observed sequence, given all current values of parameters. Sequences that better match the model will have higher probabilities
than those that do not.



Input: 
A - transition matrix
E - emission matrix
pi - initial state probabilities
states - list of states
alphabet - lets of letters comprising alphabet (e.g. ATCG)
O - observed sequence 

Output: Dictionary containing probabilities at each time point

'''

def fwd(O,A,pi,states,E):
    a = [{}]
    N = len(O)
    for state in states:
        a[0][state] = pi[state]+E[state][O[0]]
    for n in range(1,N):
        a.append({})
        if '$' in O[n]:
            for state in states:
                a[n][state] = a[n-1][state]
            continue
        for state in states:
            P=[]
            naiveP = []
            for pState in states:
                P.append(a[n-1][pState]+A[state][pState] + E[state][O[n]])
            P = logsumexp(P)
            a[n][state] = P
    return a
    
'''
Backward probabilties

Yields the probability of being in state i at time t, given all the observations for time t+1 to T,
where T is the last time point.

Similar to the foward algorithm, but moves in the opposite direction, considering the remainder of the sequence 
after the current observation.

Backward algorithm at time t = 1 will equal forward algorithm at time t = T

The forward and backward algorithms together calculate the 'smoothed probability' of being in state i at time t,
considering the entire sequence rather than prior and posterior information to the current observation. 


      Forward(t,state=i) * Backward(t,state=i)
---------------------------------------------------- = P(observation(t),state = i)
     SUM(Foward(t,state=i)*Backward(t,state=i))

Where the sum is taken over all states i in {query,null}
'''

def bkw(O,A,pi,states,E):
    b=[{}]
    N = len(O)

    for i in states:
        b[0][i] = 0

    for n in range(1,N):
        b.append({})
        if '$' in O[N-n]:
            for state in states:
                b[n][state] = b[n-1][state]
            continue
        for i in states:
            sumTerm = []
            for j in states:
                s = b[n-1][j]+A[i][j]+E[j][O[N-n]]
                sumTerm.append(s)
            P = logsumexp(sumTerm)
            b[n][i]= P
    b = b[::-1]
    return b

'''

Baum-Welch EM parameter updates

This is a custom implementation that only updates the transition matrix

'''
def update(a,b,O,states,A,E):
    gamma = [{}]
    epsilon = [{'+':{'+':0,'-':0},'-':{'+':0,'-':0}}]
    T = len(O)
    for t in range(T-1):
        gamma.append({})
        epsilon.append({'+':{'+':0,'-':0},'-':{'+':0,'-':0}})
        # Fix for appended multiple training sequences
        if ('$' in O[t]) or ('$' in O[t+1]):
            for state in states:
                gamma[t][state] = gamma[t-1][state]
                for jstate in states:
                    epsilon[t][state][jstate] = epsilon[t-1][state][jstate] 
        else:
            norm = logsumexp([a[t]['+']+b[t]['+'],a[t]['-']+b[t]['-']])
            for i in states:
                gamma[t][i]=a[t][i]+b[t][i]-norm
                for j in states:
                    numerator = a[t][i]+A[i][j]+b[t+1][j]+E[j][O[t+1]]
                    denom = []
                    for k in states:
                        for w in states:
                            denom.append(a[t][k]+A[k][w]+b[t+1][w]+E[w][O[t+1]])
                    denom = logsumexp(denom)
                    epsilon[t][i][j] =numerator-denom
    margGamma = []
    margEpsilon = []
    for i in states:
        for j in states:
            for t in range(T-1):
                margGamma.append(gamma[t][i])
                margEpsilon.append(epsilon[t][i][j])
            A[i][j] = logsumexp(margEpsilon)-logsumexp(margGamma)
            margGamma = []
            margEpsilon = []
    return A
