#!/usr/bin/env python3

# %%
import subprocess
import numpy as np
import pandas as pd
import argparse
import os
from scipy import stats
import statsmodels.api

# %%
parser = argparse.ArgumentParser()

parser.add_argument('input_path')
parser.add_argument('--VIRTUSDir', required = True)
parser.add_argument('--genomeDir_human', required = True)
parser.add_argument('--genomeDir_virus', required = True)
parser.add_argument('--salmon_index_human', required = True)
parser.add_argument('--salmon_quantdir_human', default = 'salmon_human')
parser.add_argument('--outFileNamePrefix_human', default = 'human')
parser.add_argument('--nthreads', default = '16')
parser.add_argument('-s', '--Suffix_SE', default = '.fastq.gz')
parser.add_argument('-s1', '--Suffix_PE_1', default = '_1.fastq.gz')
parser.add_argument('-s2', '--Suffix_PE_2', default = '_2.fastq.gz')
parser.add_argument('--fastq', action = 'store_true')

args = parser.parse_args()

# %%
df = pd.read_csv(args.input_path)
first_dir = os.getcwd()

# %%
series_list = []
clean_cmd = "rm -rf /tmp/*"

for index, item in df.iterrows():
    if args.fastq == False:
        dir = item["SRR"]
        sample_index = item["SRR"]
        prefetch_cmd = " ".join(["prefetch",sample_index])
        fasterq_cmd = " ".join(["fasterq-dump", "--split-files", sample_index + ".sra", "-e","16"])

        if item["Layout"] == "PE":
            fastq1 = sample_index + ".sra_1.fastq"
            fastq2 = sample_index + ".sra_2.fastq"
        elif item["Layout"] == "SE":
            fastq = sample_index + ".sra_1.fastq"
    else:
        dir = os.path.dirname(item["fastq"])
        sample_index = os.path.basename(item["fastq"])
        if item["Layout"] == "PE":
            fastq1 = sample_index + args.Suffix_PE_1
            fastq2 = sample_index + args.Suffix_PE_2
        elif item["Layout"] == "SE":
            fastq = sample_index + args.Suffix_SE

    if item["Layout"] =="PE":
        VIRTUS_cmd = " ".join([
            "cwltool --rm-tmpdir",
            os.path.join(args.VIRTUSDir, "workflow/VIRTUS.PE.cwl"), 
            "--fastq1", fastq1,
            "--fastq2", fastq2, 
            "--genomeDir_human", args.genomeDir_human, 
            "--genomeDir_virus", args.genomeDir_virus,
            "--salmon_index_human", args.salmon_index_human,
            "--salmon_quantdir_human", args.salmon_quantdir_human,
            "--outFileNamePrefix_human", args.outFileNamePrefix_human,
            "--nthreads", args.nthreads
        ])
    elif item["Layout"] =="SE":
        VIRTUS_cmd = " ".join([
            "cwltool --rm-tmpdir",
            os.path.join(args.VIRTUSDir, "workflow/VIRTUS.SE.cwl"), 
            "--fastq", fastq,
            "--genomeDir_human", args.genomeDir_human, 
            "--genomeDir_virus", args.genomeDir_virus,
            "--salmon_index_human", args.salmon_index_human,
            "--salmon_quantdir_human", args.salmon_quantdir_human,
            "--outFileNamePrefix_human", args.outFileNamePrefix_human,
            "--nthreads", args.nthreads
        ])
    else:
        print("Layout Error")

    if args.fastq == False:
        print(prefetch_cmd,"\n")
        try:
            p_prefetch = subprocess.Popen(prefetch_cmd, shell = True)
            p_prefetch.wait()
            os.chdir(dir)
        except:
            print("Download Error")

        print(fasterq_cmd,"\n")
        try:
            p_fasterq = subprocess.Popen(fasterq_cmd, shell = True)
            p_fasterq.wait()
        except:
            print("fasterq error")
    else:
        try:
            os.chdir(dir)
        except:
            print(dir," : No such directory")

    print(clean_cmd,"\n")
    try:
        p_clean = subprocess.Popen(clean_cmd,shell = True)
        p_clean.wait()
    except:
        print("clean error")

    print(VIRTUS_cmd,"\n")
    try:
        p_VIRTUS = subprocess.Popen(VIRTUS_cmd, shell = True)
        p_VIRTUS.wait()
    except:
        print("VIRTUS error")

    try:
        df_virus = pd.read_table("virus.counts.final.tsv", index_col = 0)
        series_virus = df_virus.loc[:,"rate_hit"]
        series_virus = series_virus.rename(sample_index)
        series_list.append(series_virus)
    except:
        print("virus.counts.final.tsv not found")

    os.chdir(first_dir)

# %%
summary = pd.concat(series_list, axis = 1).fillna(0).T
summary["Group"] = df["Group"].values

summary_dict = {}
Group = summary["Group"].unique()
for i in Group:
    summary_dict[i] = summary[summary["Group"] == i]

uval = pd.Series()
pval = pd.Series()

if summary["Group"].nunique() == 2:
    print("Conducting Mann-Whitney U-test")
    for i in range(0,len(summary.columns)-1):
        if summary["Group"].nunique() == 2:

            u, p = stats.mannwhitneyu(summary_dict[Group[0]].iloc[:,i],summary_dict[Group[1]].iloc[:,i], alternative = "two-sided")
            uval[summary.columns[i]] = u
            pval[summary.columns[i]] = p

fdr = pd.Series(statsmodels.stats.multitest.multipletests(pval,method = "fdr_bh")[1], index = pval.index)

summary.loc["u-value"] = uval
summary.loc["p-value"] = pval
summary.loc["FDR"] = fdr

summary.to_csv("summary.csv")

# %%
sample = summary.index[:-3]
sample_num = len(sample)
s = 0.05/(sample_num*(sample_num-1)/2)
df = pd.DataFrame(columns=sample[:-1], index=sample[1:])

for i in range(sample_num-1):
    x = [np.nan for i in range(sample_num-1)]
    for j in range(i+1,sample_num):
        x[j-1] = stats.ttest_rel(summary.iloc[i,:-1],summary.iloc[j,:-1])[1]
    df.iloc[:,i] = x
df.to_csv("ttest.csv")

with open('ttest.csv', 'a') as f:
    print("".join(["Standard (Bonferroni) = ",str(s)]), file=f)