# Bow Project - RITAL
# Ben Kabongo & Sofia Borchani
# Master DAC
# 
# Grid search

import json
import nltk
import os
import pandas as pd
import re
import sys
from itertools import combinations, product
from nltk.stem.snowball import EnglishStemmer
from nltk.stem import WordNetLemmatizer
from sklearn.decomposition import TruncatedSVD
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score, f1_score
from sklearn.model_selection import train_test_split

# Préprocessing

def delete_punctuation(text):
    punctuation = r"[\!\"\#\$\%\&\'\(\)\*\+\,\-\.\/\:\;\<\=\>\?\@\[\\\]\^\_\`\{\|\}\~\n\t]"
    text = re.sub(punctuation, " ", text)
    text = re.sub('( )+', ' ', text)
    return text

def replace_maj_word(text):
    token = '<MAJ>' # mot pour remplacer les mots en majuscules
    return ' '.join([w if not w.isupper() else token for w in delete_punctuation(text).split()])

def delete_digit(text):
    return re.sub('[0-9]+', '', text)

def first_line(text):
    return re.split(r'[.!?]', text)[0]

def last_line(text):
    if text.endswith('\n'): text = text[:-2]
    return re.split(r'[.!?]', text)[-1]

def delete_balise(text):
    return re.sub("<.*?>", "", text)

def stem(text):
    stemmer = EnglishStemmer()
    tokens = nltk.word_tokenize(text)
    stemmed_tokens = [stemmer.stem(token) for token in tokens]
    stemmed_text = " ".join(stemmed_tokens)
    return stemmed_text

def lemmatize(text):
    lemmatizer = WordNetLemmatizer()
    tokens = nltk.word_tokenize(text)
    lemmatized_tokens = [lemmatizer.lemmatize(token) for token in tokens]
    lemmatized_text = " ".join(lemmatized_tokens)
    return lemmatized_text

# Chargement des données: train

def load_movies(fname="./datasets/movies/movies1000/"):
    alltxts = [] # init vide
    labs = []
    cpt = 0
    #for cl in os.listdir(path2data): # parcours des fichiers d'un répertoire
    for cl in ['neg', 'pos']: # parcours des fichiers d'un répertoire
        for f in os.listdir(fname+cl):
            txt = open(fname+cl+'/'+f).read()
            alltxts.append(txt)
            labs.append(cpt)
        cpt+=1 # chg répertoire = cht classe
        
    all_movies_df = pd.DataFrame()
    all_movies_df['text'] = alltxts
    all_movies_df['label'] = labs
        
    return all_movies_df
    

# Grid search

def grid_search(n_preprocessors=0):

    fname="./datasets/movies/movies1000/"
    all_movies_df = load_movies(fname)

    LOG = open(f'grid_svd_{n_preprocessors}.log', 'w')

    preprocessors = [
        delete_punctuation, 
        delete_digit, 
        replace_maj_word, 
        stem,
        lemmatize
    ]
    tfidf_params = {
        'stop_words': ['english'],
        'max_df': [.5, .8, .9, 1.], 
        'min_df': [2, 3, 5], 
        'ngram_range': [(1, 2), (1, 3), (2, 2)], 
        'binary': [False, True],
        'lowercase': [False, True],
        'use_idf': [False, True],
        'sublinear_tf': [True],
        'max_features': [None, 5_000, 10_000, 20_000],
    }

    pca_n = [500, 1_000, 2_000, 4_000]

    best_params = None
    best_f1 = 0
    best_auc = 0
    
    for preprocessors_combination in combinations(preprocessors, n_preprocessors):
            
        # préprocessing
        preprocessor_func = None
        if n_preprocessors == 1:
            preprocessor_func = preprocessors_combination[0]
        elif n_preprocessors == 2:
            f, g = preprocessors_combination
            preprocessor_func = lambda x: f(g(x))
        elif n_preprocessors == 3:
            f, g, h = preprocessors_combination
            preprocessor_func = lambda x: f(g(h(x)))
        elif n_preprocessors == 4:
            f, g, h, i = preprocessors_combination
            preprocessor_func = lambda x: f(g(h(i(x))))
        elif n_preprocessors == 5:
            f, g, h, i, j = preprocessors_combination
            preprocessor_func = lambda x: f(g(h(i(j(x)))))
           
        for tfidf_param_combination in product(*tfidf_params.values()):
            # paramètres de tf-idf
            tfidf_param_dict = dict(zip(tfidf_params.keys(), tfidf_param_combination))
            tfidf = TfidfVectorizer(preprocessor=preprocessor_func, **tfidf_param_dict)

            # train/test split
            X_text_train, X_text_test, y_train, y_test = train_test_split(all_movies_df['text'], 
            all_movies_df['label'], test_size=0.2, random_state=42)

            X_train = tfidf.fit_transform(X_text_train)
            X_test = tfidf.transform(X_text_test)

            for n in pca_n:
                svd = TruncatedSVD(n_components=n)

                X_train_svd = svd.fit_transform(X_train)
                X_test_svd = svd.transform(X_test)

                lr = LogisticRegression()
                lr.fit(X_train_svd, y_train)

                # evaluation
                y_pred = lr.predict(X_test_svd)
                f1 = f1_score(y_test, y_pred)
                auc = roc_auc_score(y_test, y_pred)

                print('---------------------------------------------------')
                print('Params:',
                    '\n\tpreprocessors:', preprocessors_combination, 
                    '\n\ttfidf_params:', tfidf_param_dict,
                    '\n\tSVD:', n
                )
                print('F1-score:', f1)
                print('AUC:', auc)

                LOG.write('\n\n')
                LOG.write('Params:' +
                    '\n\tpreprocessors : ' + str(preprocessors_combination) +
                    '\n\ttfidf_params : ' + str(tfidf_param_dict) +
                    '\n\tSVD : ' + str(n)
                )
                LOG.write('\nF1-score: ' + str(f1))
                LOG.write('\nAUC : '+ str(auc))
                if f1 > .90 and auc > .90:
                    LOG.write('*******************************************')

                if f1 > best_f1:
                    best_f1 = f1
                    best_auc = auc
                    best_n = n
                    best_params = {
                        'preprocessors': preprocessors_combination, 
                        'tfidf_params': tfidf_param_dict,
                        'svd': n
                    }

    print('---------------------------------------------------')
    print('Best params:', best_params)
    print('Best F1-score:', best_f1)
    print('Best AUC:', best_auc)

    return best_params


# main

if __name__ == '__main__':
    n_preprocessors = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    best_params = grid_search(n_preprocessors=n_preprocessors)
    json.dump(best_params, open(f'best_params_{n_preprocessors}_save.json', 'wb'))