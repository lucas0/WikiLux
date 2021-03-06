import resource
import filecmp
from sklearn.utils import shuffle
import tensorflow as tf
import subprocess
import json
import seaborn as sns
import matplotlib.pyplot as plt
import re
import hashlib
import numpy as np
import os,sys
import pickle
import gensim.models as w2v
import pandas as pd
import nltk
import generateFeatures as feat
tf.compat.v1.logging.set_verbosity(tf.compat.v1.logging.FATAL)

filename = sys.argv[0]
cwd = os.path.abspath(filename+"/..")

modelpath = cwd+"/w2vModel"
data_dir = cwd+"/data"
bert_dir = cwd+"/res/bert"
hash_path = cwd+"/data/hash.txt"
spec_dir = cwd+"/res/specificity/Domain-Agnostic-Sentence-Specificity-Prediction"

#max num of words in a sentence
MAX_SENT_LEN = 3000
EMB_DIM_SIZE = 300
BERT_DIM = 786
FEATS_DIM = 94

def clean_text(string):
    """
    Tokenization/string cleaning for all datasets except for SST.
    Original taken from https://github.com/yoonkim/CNN_sentence/blob/master/process_data.py
    """
    string = re.sub(r"[^A-Za-z0-9(),!?\'\`]", " ", string)
    string = re.sub(r"\'s", " \'s", string)
    string = re.sub(r"\'ve", " \'ve", string)
    string = re.sub(r"n\'t", " n\'t", string)
    string = re.sub(r"\'re", " \'re", string)
    string = re.sub(r"\'d", " \'d", string)
    string = re.sub(r"\'ll", " \'ll", string)
    string = re.sub(r",", " , ", string)
    string = re.sub(r"!", " ! ", string)
    string = re.sub(r"\(", " \( ", string)
    string = re.sub(r"\)", " \) ", string)
    string = re.sub(r"\?", " \? ", string)
    string = re.sub(r"\s{2,}", " ", string)
    return string.strip()

def pos(sentence):
    tokens = nltk.word_tokenize(sentence)
    tagsAndTokes = nltk.pos_tag(tokens)
    justTags = " ".join([e[1] for e in tagsAndTokes])
    return justTags

def save_p(filename, data):
    with open(filename, "wb") as p:
    #pickle.dump(data, open(filename, 'wb'), protocol=4)
        pickle.dump(data, p)

def read_p(filename):
    with open(filename, "rb") as f:
        return pickle.load(f)

def check_hash(df_hash, num_folds, stage="data"):
    print(stage.upper(), " CHECK> Checking Hash Path on: ",hash_path)
    if os.path.exists(hash_path):
        with open(hash_path, "r") as h:
            lines = h.readlines()
            old_folds = lines[1][:-1]
            if stage is "data":
                old_hash = lines[0][:-1]
            if stage is "bert":
                old_hash = lines[2][:-1]
            if stage is "features":
                old_hash = lines[3][:-1]
            if stage is "complexity":
                old_hash = lines[4][:-1]
            if stage is "specificity":
                old_hash = lines[5][:-1]
            if stage is "w2v":
                old_hash = lines[6][:-1]
            print("Old and New Hash: ",old_hash[:5],df_hash[:5]," Same? ", (old_hash == df_hash))
            print("Old and New #folds:",old_folds, num_folds, " Same? ", (int(old_folds)==num_folds), "\n")
        if (old_hash == df_hash) and (int(old_folds) == num_folds):
            return True
    return False

def savehash(line, content):
    with open(hash_path, "r") as h:
        data = h.readlines()
        data[line] = content+"\n"
    with open(hash_path, "w") as h:
        h.writelines(data)

def reset_hash():
    with open(hash_path, "r+") as f:
        lenlin = len(f.readlines())
    with open(hash_path, "w+") as f:
        for i in range(lenlin):
            f.write("0\n")

#run concat+normalize.py inside dataset/ before loading data
def load_data(emb_type='w2v', collapse_classes=False, fold=None, num_folds=1, random_state=None, force_reload=False):
    print('Loading data from',data_dir)
    data = pd.read_csv(data_dir+"/dataset_wiki_clean.csv", sep=',')

    #if force_reload: reset_hash()
    data = data[data['body'].apply(lambda x: isinstance(x, str))]
    data = data[data['body'].map(len) > 1000]
    data = data.reset_index()
    #data = data.sample(frac=0.01, random_state=random_state)
    #data = data.sample(frac=0.005, random_state=random_state)
    data = data.sample(frac=0.115, random_state=random_state+1)
    json_data = data.to_json().encode()
    df_hash = hashlib.sha256(json_data).hexdigest()

    labels = ['SPOV', 'POV']

    labels_idx = [labels.index(label) for label in labels]
    labels_one_hot = np.eye(len(labels))[labels_idx]
    label_to_oh = {label:labels_one_hot[labels.index(label)] for label in labels}

    print("MEMORY: ",resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)

    assert (num_folds > 2), "Needs at least three folds for Dev/Train/Test to be different from each other"
    #generate and save the folds:
    for fold in range(num_folds):
        bucket_size = int(len(data.index)/num_folds)
        fold_dev = fold+1
        if fold == num_folds-1:
            fold_dev = 0

    if not check_hash(df_hash, num_folds):
        print("Processing New Data...")

        data = [(clean_text(pd.Series(e[1])['body']),pd.Series(e[1])['label'])for e in list(data.iterrows())]
        #data = [(clean_text(pd.Series(e[1])['body']),pd.Series(e[1])['label'])for e in list(data.iterrows()) if not pd.Series(e[1])['body'].isnull()]
        df = pd.DataFrame(data, columns=["body","label"])

        lens = pd.Series([len(e.split(" ")) for e in df['body'].values])
        df = df[lens < MAX_SENT_LEN]
        num_entries = len(df)
        lens = np.asarray([len(e.split(" ")) for e in df['body'].values])
        df = df.reset_index(drop=True)
        df.to_csv(data_dir+'/data.csv', index=False)

        #plots the data distribution by number of words
        print("Number of entries: ", num_entries)
        print("NPOV/SPOV: ",df.groupby('label').count())
        print("Mean and Std of number of words per document: ",np.mean(lens),np.std(lens))
        #sns.distplot(lens)
        #plt.show()

        #check if new bert should be generated
        if not check_hash(df_hash, num_folds, stage="bert"):
            inputfile = cwd+'/res/bert/input.txt'
            #copy sentences so BERT is generated
            with open(inputfile, 'w+') as f:
                for i,e in df.iterrows():
                    f.write(e['body']+'\n')

            #Generate BERT embeddings if data is new
            #removes the output file so a new one is generated
            cmd0 = "rm "+cwd+"/res/bert/output4layers.json"
            subprocess.call(cmd0, shell=True, cwd = bert_dir)

            #generates new BERT embeddings
            cmd1 = "python3 extract_features.py   --input_file=input.txt   --output_file=output4layers.json   --vocab_file=$BERT_BASE_DIR/vocab.txt   --bert_config_file=$BERT_BASE_DIR/bert_config.json   --init_checkpoint=$BERT_BASE_DIR/bert_model.ckpt   --layers=-1,-2,-3,-4  --max_seq_length=512   --batch_size=32"
            subprocess.call(cmd1, shell=True, cwd = bert_dir)
            print("BERT Embeddings Saved")
            savehash(line=2, content=df_hash)


        ###################################
        ############# FEATURES ############
        ###################################

        #check if new linguistic features should be generated
        if not check_hash(df_hash, num_folds, stage="complexity"):
            #Generate the features ndarray and save it to a pickle
            try:
                feat.generate_complexity()
            except Exception as e:
                print("Error on [generateFeatures.py] generateComplexity()!", e)
                sys.exit(1)
            savehash(line=4, content=df_hash)
        if not check_hash(df_hash, num_folds, stage="specificity"):
            feat.generate_specificity()
            savehash(line=5, content=df_hash)
        if not check_hash(df_hash, num_folds, stage="features"):
            features = []
            for idx,e in df.iterrows():
                feature = feat.vectorize(e[0],idx)
                features.append(feature)
            features = np.array(features).astype(np.float)
            print(features.shape)
            save_p(data_dir+"/features", features)
            print("Generated Features. Saved to pickle.")
            savehash(line=3, content=df_hash)

        features = read_p(data_dir+"/features")

        #normalize features
        features = np.nan_to_num(features)
        features_t = features.T
        for c in range(features_t.shape[0]):
            row = features_t[c]
            features_t[c] = np.interp(row, (np.min(row), np.max(row)), (-2, +2))
        features = features_t.T
        print(features.shape)

        print("MEMORY AFTER FEATURES: ",resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)

        ###################################
        ############### W2V ###############
        ###################################

        #if not check_hash(df_hash, num_folds, stage="w2v"):
        #    #generate w2v embeddings from data
        #    w2v_model = w2v.KeyedVectors.load_word2vec_format(cwd+'/data/GoogleNews-vectors-negative300.bin', binary=True)
        #    embeddings = []
        #    for idx, row in df.iterrows():
        #        words = row['body'].split(" ")
        #        words = filter(lambda x: x in w2v_model.vocab, words)
        #        embedding = [w2v_model.wv[word] for word in words]
        #        masked = np.zeros((MAX_SENT_LEN, EMB_DIM_SIZE))
        #        mask_len = min(len(embedding),MAX_SENT_LEN)
        #        masked[MAX_SENT_LEN-mask_len:] = embedding[:mask_len]
        #        embeddings.append(masked)

        #    embeddings = np.array(embeddings, dtype=np.float32)
        #    save_p(data_dir+"/masked_embeddings", embeddings)
        #    print("Masked Embeddings Saved")
        #    savehash(line=6, content=df_hash)

        #print("MEMORY AFTER W2V: ",resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)

        #########################################
        ## CONCATENATION, SHUFFLING AND SAVING ##
        #########################################

        #delete folds folders
        subprocess.call("rm -rf "+data_dir+"/folds/*", shell=True, cwd=data_dir)

        #creates the shuffle order
        index_shuf = list(range(len(df)))

        #LABELS
        print(">>>>>")
        print(">>>",df['label'].values.tolist())
        print(label_to_oh)
        labels = [label_to_oh[label].tolist() for label in df['label'].values.tolist()]
        labels = [labels[i] for i in index_shuf]
        label_folds = np.array_split(labels, num_folds)
        for i in range(num_folds):
            fold_dir = data_dir+"/folds/"+str(i)
            os.mkdir(fold_dir)
            save_p(fold_dir+"/labels", label_folds[i])

        ##W2V
        #embeddings = read_p(data_dir+"/masked_embeddings")
        #features_broad = np.array([features] * MAX_SENT_LEN)
        #features_broad = np.swapaxes(features_broad, 0,1)
        #w2v_post_data = np.concatenate((features_broad,embeddings), axis=2)
        #print("W2V+Features shape: ",w2v_post_data.shape)
        #w2v_post_data = [w2v_post_data[i] for i in index_shuf]
        #only_w2v_folds = np.array_split(embeddings, num_folds, axis=0)
        #w2v_folds = np.array_split(w2v_post_data, num_folds, axis=0)
        #for i in range(num_folds):
        #    fold_dir = data_dir+"/folds/"+str(i)
        #    save_p(fold_dir+"/w2v", w2v_folds[i])
        #    save_p(fold_dir+"/only_w2v", only_w2v_folds[i])

        #BERT
        with open(bert_dir+"/output4layers.json", "r+") as f:
            bert = [json.loads(l)['features'][0]['layers'][0]['values'] for l in f.readlines()]
        bert_post_data = np.concatenate((features,bert), axis=1)
        print("BERT+Features shape: ",bert_post_data.shape)
        bert_post_data = [bert_post_data[i] for i in index_shuf]
        bert_folds = np.array_split(bert_post_data, num_folds)
        only_bert_folds = [bert[i] for i in index_shuf]
        only_bert_folds = np.array_split(bert, num_folds)
        for i in range(num_folds):
            print("saving bert fold ",str(i), bert_folds[i].shape)
            fold_dir = data_dir+"/folds/"+str(i)
            save_p(fold_dir+"/bert", bert_folds[i])
            save_p(fold_dir+"/only_bert", only_bert_folds[i])

        #labels, w2v_post_data, bert_post_data = shuffle(labels, w2v_post_data, bert_post_data, random_state=0)

        print("MEMORY AFTER FOLDS SAVING: ",resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)

        print('Generation of data done!')

        savehash(line=0, content=df_hash)
        savehash(line=1, content=str(num_folds))

        return load_data(emb_type=emb_type, collapse_classes=collapse_classes, fold=fold, num_folds=num_folds, random_state=random_state)

    else:
        print("Reading already processed data")
        #returns the selected emb type (bert/w2v)
        test_data = read_p(data_dir+"/folds/"+str(fold)+"/"+emb_type)
        test_target = read_p(data_dir+"/folds/"+str(fold)+"/labels")

        dev_data = read_p(data_dir+"/folds/"+str(fold_dev)+"/"+emb_type)
        #dev_data = np.ndarray(dev_data)
        dev_target = read_p(data_dir+"/folds/"+str(fold_dev)+"/labels")

        train_data_filenames = [data_dir+"/folds/"+str(i)+"/"+emb_type for i in range(num_folds) if i not in [fold,fold_dev]]
        train_data = np.concatenate([read_p(fn) for fn in train_data_filenames], axis=0)
        train_target_filenames = [data_dir+"/folds/"+str(i)+"/labels" for i in range(num_folds) if i not in [fold,fold_dev]]
        train_target = np.concatenate([read_p(fn) for fn in train_target_filenames], axis=0)

        return train_data, train_target, dev_data, dev_target, test_data, test_target, label_to_oh

