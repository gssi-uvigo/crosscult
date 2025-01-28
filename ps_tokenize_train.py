#!/Library/Frameworks/Python.framework/Versions/Current/bin/python3
# Este programa sirve para entrenar modelos Word2Vec

import gensim
from gensim.models import Word2Vec
# from gensim.models import Phrases
# from gensim.models.phrases import Phraser
# from gensim.models.word2vec import LineSentence
from gensim.models.callbacks import CallbackAny2Vec
from nltk.stem.porter import *
from nltk.tokenize import word_tokenize, RegexpTokenizer
import nltk
import re
from pycorenlp import StanfordCoreNLP
import pickle
import os
import sys
from px_aux import saveFile as _saveFile

if len(sys.argv) < 2:
	print("Usa: "+sys.argv[0]+" fichero_con_los_textos_de_entrenamiento")  
	exit(-1)

print("Reading input file...")
mypath = sys.argv[1]   # este es el fichero con todos los textos unidos, lo lógico es que sea un fichero.w (antes se usaba "./texts/historical_modify.txt")
fp = open(mypath)
data = fp.read()

nlpStanfordBroker = StanfordCoreNLP('http://localhost:9000')    # inicializamos un broker hacia el servicio de Stanford, que debe estar corriendo en esta máquina
puntuation = ['.', ',', '?', '¿', ')', '(', ']', '[', '\'', '/', '%', '...', '$', '–', '=', '‘', '¡', '!', '´', ':', ';', '’', '--', '``', "''", '-', '\'s', "'", "bc", "b.c.e.", "etc.", "i.e.", "e.g.", "cf.", "mt.", "st.", "mr.", "ms.", "dr."]

print("Pre-processing input file...")
tokenizer = nltk.data.load('tokenizers/punkt/english.pickle')
sentences = tokenizer.tokenize(data.strip(), realign_boundaries=True)  # lista de frases
totalSentences = len(sentences)

# se supone que recibe un match de 3 grupos y devuelve el segundo, es para quitarle el tercero si es un punto (pero no veo que pase nunca)
def remove_last_punt(match):
	return match.group(2)

sentencesTokenizedLower = []

i = 0
for sentence in sentences:   # cada sentence es una frase, una cadena
	res = nlpStanfordBroker.annotate(sentence, properties={'annotators': 'tokenize,ssplit,pos,lemma', 'outputFormat': 'json'})
	# res tiene el formato que se puede ver en la sec 6.1

	lemmasSentenceLower = []   # lista de lemmas de las palabras de una frase, en minúscula
	for palabra in res["sentences"][0]["tokens"]: # palabra son las distintas palabras identificadas en sentence
		lemma = palabra["lemma"].lower()  # lemma es la forma canónica de la palabra en minúscula

		isNumber = re.search("(\d)+\D?(\d)*", lemma)  # devuelve el match si es un número o None si no
		
		# elimina del texto ciertas palabras
		if palabra["originalText"] not in puntuation and lemma not in puntuation and len(lemma) > 0 and palabra["pos"] not in [",", ".", "PRP", "PRP$", "TO", "IN", "DT", "CC", "SYM", "UH"] and not isNumber:
			removedPunt = re.sub("(\W*)([a-zA-Z_0-9].*[a-zA-Z_0-9])(\W*)", remove_last_punt, lemma) # le quita el punto final si lo tiene
			lemmasSentenceLower.append(removedPunt)

	sentencesTokenizedLower.append(lemmasSentenceLower)

sentecesLowerTrain = sentencesTokenizedLower # entrada para entrenar los modelos simples

# esto parece sólo para generar el modelo compuesto, con la fase de unir palabras
# phrasesLower = Phrases(sentencesTokenizedLower, min_count=5)
# bigramLower = Phraser(phrasesLower)
# phrasesSecond = Phrases(bigramLower[sentencesTokenizedLower], min_count=5)
# bigramLower = Phraser(phrasesSecond)
# sentecesLowerTrainCompound = bigramLower[sentencesTokenizedLower] # entrada para entrenar los modelos compuestos

class EpochLogger(CallbackAny2Vec):
     '''Callback to log information about training'''

     def __init__(self):
        self.epoch = 0

     def on_epoch_begin(self, model):
        print("Epoch #{} start".format(self.epoch))

     def on_epoch_end(self, model):
        print("Epoch #{} end".format(self.epoch))
        self.epoch += 1


def trainAndSave(sentences, w, m_c, i):
	name = "agilc_W" + str(w) + "_MC" + str(m_c) + "_I"+str(i)
	print("Training "+name)
	m = Word2Vec(sentences, size=300, workers=4, window=w, min_count=m_c, iter=i)   # siempre 300 neuronas
	m.save("./models/" + name)

trainAndSave(sentecesLowerTrain, 10, 20, 1000)   # modelo simple, Window=10, MC=10, Iteracons=1000
sys.exit(0)


#Compounds
trainAndSave(sentecesLowerTrainCompound, 5, 1, 50, compound=True)
trainAndSave(sentecesLowerTrainCompound, 10, 1, 50, compound=True)
trainAndSave(sentecesLowerTrainCompound, 5, 5, 50, compound=True)

#Single
trainAndSave(sentecesLowerTrain, 5, 1, 50)
trainAndSave(sentecesLowerTrain, 10, 1, 50)
trainAndSave(sentecesLowerTrain, 5, 5, 50)


