# -*- coding: utf-8 -*-

# Flask es un módulo para lanzar un servidor que gestiona solicitudes HTTP. Permite asociar una función con cada llamada
from flask import Flask, render_template, request, flash, json, jsonify, redirect, url_for, send_from_directory

# funciones del pp_routes.py que se ejecutan al llegar una solicitud Flask
from pp_routes import getSimilarWords, getDistance, setStoredQA, getTrainingTexts, getVocabModel, getProcessingStep123Files, getFile, getEntityFile, recalculateEntities


# URL donde atienden la DBpedia (consultas SPARQL) y la DBpedia SpotLight
from px_aux import URL_DB as _URL_DB, URL_DB_SL_annotate as _URL_DB_SL_annotate, URL_Stanford as _URL_Stanford, StanfordBroker as _StanfordBroker
from px_DB_Manager import DBManager as _DBManager
from px_aux_add_suffix import processContent as _processContent     # para añadir los sufijos

# gensin son los módulos de doc2vec y word2vec
from gensim.models.doc2vec import Doc2Vec, TaggedDocument
from nltk.tokenize import sent_tokenize
# módulo para acceder a las herramientas de Stanford
from pycorenlp import StanfordCoreNLP
import threading
import gensim
from werkzeug.utils import secure_filename
from gensim.models import KeyedVectors
from gensim.models import Phrases, Word2Vec
from gensim.models.word2vec import LineSentence
# requests es un módulo para realizar peticiones HTTP
import requests
from requests_futures.sessions import FuturesSession
import pickle
from requests.utils import quote
import operator
from nltk.tokenize import RegexpTokenizer
import re

from collections import OrderedDict

import os
from os import listdir
from os.path import isfile, join

import urllib.parse
from string import Template
import numpy

from scipy.spatial.distance import cosine
from scipy.sparse.csgraph import dijkstra
import uuid
from gensim.models.callbacks import CallbackAny2Vec

import time


# El directorio donde están los modelos entrenados de Word2Vec
MODELS_FOLDER = './models/'
DB_ENTITIES_FOLDER = "./DBentities/"

# El fichero con el texto T por defecto de la demo
DEFAULT_TEXT = 'defaultText.txt'

MODEL_GOOGLE_PORT = 9100

# fichero con información de las entidades de la DBpedia identificadas en los textos de entrenamiento
# fichero generado el programa ps_2buildDbpediaInfoFromTexts.py
# debe estar en el directorio MODELS_FOLDER
# DBPEDIA_INFO_ABOUT_TRAINING = "historical_modify.txt.p"
DBPEDIA_INFO_ABOUT_TRAINING = "originales.s.w.p"

# fijamos las pregunta/respuesta por defecto
DEFAULT_QUESTION = "Who led the Persians in the battle of Thermopylae?"
DEFAULT_ANSWER = "Xerxes I"





# comenzamos a hacer cosas

# Creamos la app de Flask que va a gestionar las solicitudes HTTP
app = Flask(__name__)

# leemos la información de la DBpedia sobre las entidades de los textos de entrenamiento
historicalDBpediaDataMod = pickle.load(open(DB_ENTITIES_FOLDER+DBPEDIA_INFO_ABOUT_TRAINING, "rb" ))
dbManagerHistorical = _DBManager()
dbManagerHistorical.setDictionaries(historicalDBpediaDataMod)

# list con tuplas de (pregunta, respuesta)
listQATuplas = []

# leemos listQATuplas del fichero donde las almacenamos
try:
	listQATuplas = pickle.load(open( "storedQA.p", "rb" ))
except:
	pass



#####  Definición de clases auxiliares



# clase de un objeto del modelo W2V de Google
# se supone que le pide los datos del modelo a localhost:9100 
# en principio sólo se instancia la clase, pero no se usa, por lo que no es necesario ese proceso en el 9100

class ProxyGoogleModel:

	def __getattribute__(self, attr):
		if attr in ["vocab", "inVocab", "rawVocab"] :
			return super(ProxyGoogleModel, self).__getattribute__(attr)

		if attr == "syn1neg":
			return None

		def auxFunction(*argv, **kwargs):
			path = "http://localhost:" + str(MODEL_GOOGLE_PORT) + "/model/" + attr
			if len(argv) > 0:
				path += "?"
				i = 0
				for a in argv:
					path += "arg" + str(i) + "=" + str(a)
					if i < len(argv) - 1 or len(kwargs) > 0:
						path += "&"
					i += 1
				i = 0
				for a in kwargs:
					path += a + "=" + str(kwargs[a])
					if i < len(kwargs) - 1:
						path += "&"
					i += 1

			app.logger.info(path)
			r = requests.get(path, stream=True)
			return pickle.loads(r.raw.read(), encoding='latin1')

		return auxFunction

	def vocab(self, item):
		r = requests.get("http://localhost:" + str(MODEL_GOOGLE_PORT) + "/model/vocab/get?arg1="+item, stream=True)
		return pickle.loads(r.raw.read(), encoding='latin1')

	def inVocab(self, item):
		r = requests.get("http://localhost:" + str(MODEL_GOOGLE_PORT) + "/model/vocab/__contains__?arg1="+item, stream=True)
		return pickle.loads(r.raw.read(), encoding='latin1')

	def rawVocab(self):
		r = requests.get("http://localhost:" + str(MODEL_GOOGLE_PORT) + "/model/vocab/keys", stream=True)
		return pickle.loads(r.raw.read(), encoding='latin1')

# Fin clase ProxyGoogleModel



# Esto es un Proxy a un modelo W2V entrenado por nosotros
# se supone que, a diferencia de Google, lee los datos del modelo de un fichero
# vamos a hablar de un Pmodel para referirnos a este objeto, y a un Wmodel para referirnos al modelo W2V que es el objeto controlado 
class ModelTrainedProxy:

	# la variable/atributo 'model' de un objeto de la clase ModelTrainedProxy es el modelo Gensim, un Wmodel
	def __init__(self, pathModel, binary=False):
		if binary:
			self.wModel = KeyedVectors.load_word2vec_format(pathModel, binary=True)
		else:
			# nosotros llamamos sin 'binary' y se ejecuta esto
			self.wModel = KeyedVectors.load(pathModel)

	def __getattribute__(self, attr):
		if attr == "inVocab":
			return object.__getattribute__(self, 'inVocab')
		elif attr == "vocab":
			return object.__getattribute__(self, 'vocab')
		elif attr == "indexVocab":
			return object.__getattribute__(self, 'indexVocab')
		elif attr == "rawVocab":
			return object.__getattribute__(self, 'wModel').wv.vocab
		elif attr == "distance":
			return object.__getattribute__(self, 'wModel').wv.distance
		elif attr == "closer_than":
			return object.__getattribute__(self, 'wModel').wv.closer_than
		elif attr == "syn1neg":
			return object.__getattribute__(self, 'wModel').syn1neg
		elif attr == "syn1":
			return object.__getattribute__(self, 'wModel').syn1
		elif attr == "get_vector":
			# esto invoca al método 'get_vector' de Gensim para obtener el vector característico
			return object.__getattribute__(self, 'wModel').wv.get_vector

		# si el atributo/función solicitado no era uno de los anteriores,
		_wmodel = object.__getattribute__(self, 'wModel')
		return object.__getattribute__(_wmodel, attr)

	def inVocab(self, name):
		_wmodel = object.__getattribute__(self, 'wModel')
		return name in _wmodel.wv.vocab

	def vocab(self, name):
		_wmodel = object.__getattribute__(self, 'wModel')
		return _wmodel.wv.vocab[name]

    # no parece usasrse
	def indexVocab(self, name):
		_wmodel = object.__getattribute__(self, 'wModel')
		try: 
			return list(_wmodel.wv.vocab.keys()).index(name)
		except:
			return None

# Fin clase ModelTrainedProxy




# clase del objeto principal de esta demo

class DemoDoc:

	# en la inicialización recibe el endpoint del Stanford
	def __init__(self):
		# La información sobre cada modelo se guarda en un diccionario llamado 'dict_models', con clave el nombre del modelo y valor un objeto ModelTrainedProxy (un pmodel)
		
		# Añadimos el gestor del modelo de Google. No se usa, así que probablemente ni se haya lanzado el proceso que escucha
		self.dict_models = {"google": ProxyGoogleModel()}
		
		# Cargamos todos los modelos de Word2Vec en el diccionario 'dict_models'
		# se trata de aquellos del directorio 'models' que no tengan un punto en su nombre
		for filename in os.listdir(MODELS_FOLDER):
			if len(filename.split(".")) == 1:
				# inicializa un objeto Pmodel por cada uno de los modelos disponibles
				_pm = ModelTrainedProxy(MODELS_FOLDER+filename)
				_pm.init_sims()  # esto inicializa los vectores, parece una llamada al proxy, pero realmente se propaga a una llamada al wmodel correspondiente
				# Guarda uno a uno los proxies modelos (Pmodel) en el diccionario 'dict_models'
				self.dict_models[filename] = _pm

		# crea el objeto gestor de las solicitudes al Stanford
		self.standfordCoreNLP = StanfordCoreNLP(_URL_Stanford)
		
		self.stanfordBroker = _StanfordBroker()


	# para identificar las palabras que contiene un texto, haciendo uso de Stanford
	# recibe un texto y devuelve las palabras que identifica Stanford
	# devuelve una lista de diccionarios, uno por palabra con las claves [offset, word, POS, lemma], la primera número y el resto cadenas
	def getWordsInText(self, text):
		palabras = self.stanfordBroker.identifyWords(text)
		result = [dict([('offset', x["characterOffsetBegin"]), ('word', x["originalText"]), ('POS', x["pos"]), ('lemma', x["lemma"])]) for x in palabras]
		
		return result



	# recibe las palabras identificadas en un texto, elimina los duplicados, y se queda solamente con las interesantes (selected)
	# recibe una lista de diccionarios, uno por palabra con las claves [offset, word, POS, lemma]
	# devuelve una lista de diccionarios, uno por palabra con las claves [offset, word, POS, lemma], la primera número y el resto cadenas
	def getInterestingWordsInText(self, text, selectedPOS = ["NN, NNS"]):
		palabras = self.getWordsInText(text) # pide todas las palabras que se identifiquen en el texto
		
		usefulQuestionWords = []
		checkDupWords = []
		for w in palabras:
			if w["POS"] in selectedPOS and w["lemma"] not in checkDupWords:
				usefulQuestionWords.append(w)
				checkDupWords.append(w["lemma"])

		return usefulQuestionWords

# Fin clase DemoDoc







# Comienza la ejecución real de la aplicación

fecha = "Fecha lanzamiento del proceso = " + time.strftime("%c")

# creamos el objeto 'demo' de la clase DemoDoc 
demo = DemoDoc()

# leemos el texto por defecto de la demo
defaultTextFile = open(DEFAULT_TEXT, "r")
defaultText = defaultTextFile.read()


# No hace nada más, excepto al final ponerse a escuchar en el puero 5000 las solicitudes Flask





##### Llamadas Flask y funciones asociadas

# filtro para añadir 'selected' a la opción por defecto (sólo para los modelos?)
@app.template_filter('isDefaultOption')
def isDefaultOption(s):
    if s.startswith('0_'):
    	return "selected"

    return ""

# filtro para cambiarle el nombre a una opción y que no sea la por defecto (sólo para los modelos?)
@app.template_filter('removeDefault')
def removeDefault(s):
    if s.startswith('0_'):
    	return s[2::]

    return s


# Flask routes binding
app.add_url_rule("/getSimilarWords", "getSimilarWords", getSimilarWords)
app.add_url_rule("/getDistance", "getDistance", getDistance)
app.add_url_rule("/setStoredQA", "setStoredQA", setStoredQA, methods=["POST"])
app.add_url_rule("/getTrainingTexts", "getTrainingTexts", getTrainingTexts)
app.add_url_rule("/getVocabModel", "getVocabModel", getVocabModel)
app.add_url_rule("/getProcessingStep123Files", "getProcessingStep123Files", getProcessingStep123Files)
app.add_url_rule("/getFile", "getFile", getFile)
app.add_url_rule("/recalculateEntities", "recalculateEntities", recalculateEntities)

# app.add_url_rule("/getEntityFile", "getEntityFile", getEntityFile)


from buildCorpus.pp_routesCorpus2 import buildCorpus2
from buildCorpus.pp_routesCorpus import getWikicatsFromText, buildCorpus, getWikicatUrls


app.add_url_rule("/getWikicatsFromText", "getWikicatsFromText", getWikicatsFromText, methods=["POST"])
app.add_url_rule("/buildCorpus", "buildCorpus", buildCorpus, methods=["POST"])
app.add_url_rule("/buildCorpus2", "buildCorpus2", buildCorpus2, methods=["POST"])
app.add_url_rule("/getWikicatUrls", "getWikicatUrls", getWikicatUrls)

@app.route('/corpus',  methods=["GET", "POST"])
def hello_corpus():
	return render_template('./template_corpus.html', parDefaultText=defaultText)








@app.route('/',  methods=["GET", "POST"])
def hello_world():
	return render_template('./template.html', parFecha=fecha, parModels=availableModels(), parStoredQA=listQATuplas, parDefaultText=defaultText, parQuestion=DEFAULT_QUESTION, parAnswer=DEFAULT_ANSWER)


def availableModels():
	mypath = MODELS_FOLDER
	onlyfiles = [f for f in listdir(mypath) if isfile(mypath+f) and not f.startswith('.') and len(f.split('.'))==1]
	onlyfiles.sort()

	return onlyfiles


# esto sólo se usa para servir el style.js
@app.route('/js/<path:path>')
def send_js(path):
    return send_from_directory('js', path)






# Compute softmax values for each sets of scores in x.
def softmax(x):
    e_x = numpy.exp(x - numpy.max(x))
    return e_x / e_x.sum(axis=0)



# esto parece no usarse
# class FuncThread(threading.Thread):
#     def __init__(self, target, *args):
#         self._target = target
#         self._args = args
#         threading.Thread.__init__(self)
#  
#     def run(self):
#         self._target(*self._args)






@app.route('/algorithmA2', methods=["GET", "POST"])
def AlgorithmA2():


	# calcula y gestiona las probabilidades de todos los modelos, usa la próxima clase, ModelVectorProbabilites
	class AllModelsVectorProbabilities:

		# recibe la lista de palabras de la pregunta (sus lemas en minúsculas)
		# se crea la lista 'listModelVectorProbabilities', con un objeto por modelo, con dos campos: 'name' el nombre del modelo, y 'model' el objeto ModelVectorProbabilites de ese modelo
		def __init__(self, words="ALL"):
			self.listModelVectorProbabilities =[]
			# la variable 'dict_models' del objeto demo (clase DemoDoc) es un diccionario con todos los modelos (objetos de la clase ModelTrainedProxy) con clave su nombre
			for n in demo.dict_models:  
				if n != "google": # el modelo de google realmente no se usa (probablemente ni siquiera se haya lanzado el proceso que  sirve su informatción)
					self.listModelVectorProbabilities.append( {"name": n , "model": ModelVectorProbabilites(n, words)})

		# devuelve el objeto ModelVectorProbabilites correspondiente al nombre del modelo que se recibe como parámetro
		def getMVP(self, modelname):		
			for model in self.listModelVectorProbabilities:
				if model["name"] == modelname:
					return model["model"]
			
			return None

		# devuelve una lista con un objeto {'name':modelname, 'syn1negs': syn1negs del nameMVP} por cada uno de los MVP
		def getSyn1negs(self):
			return list(map(lambda x: {"name": x["name"], "syn1negs": x["model"].getSyn1negs()}, self.listModelVectorProbabilities))

		# devuelve un dict  con clave elnombre del modelo M y valor M.getSyn1negsStr() 
		def getSyn1negsStr(self):
			return dict(map(lambda x: (x["name"], x["model"].getSyn1negsStr()), self.listModelVectorProbabilities))

		# para ordenar calcular las probabilidades de todos los modelos para la entidad que recibe
		def run (self, entity):
			for model in self.listModelVectorProbabilities:
				# se hace run() uno a uno de todos los ModelVectorProbabilites, y se sustituyen en listModelVectorProbabilities por lo que devuelve la llamada
				model["model"].run(entity)   

		# devuelve una lista con los nombres de los modelos en los cuales la última entidad evaluada no existía en su vocabulario
		def getModelsNotHaveLastWord(self):
			statusList = list(map(lambda x: {"name":  x["name"], "inModel": x["model"].lastEntityInModel}, self.listModelVectorProbabilities))
			notHaving = list(filter(lambda x: x["inModel"] == False, statusList))
			return list(map(lambda x: x["name"], notHaving))
	
	# fin de la clase AllModelsVectorProbabilities
	


	# gestiona las probabilidades de las palabras en un modelo
	class ModelVectorProbabilites:

		# en la inicialización se recibe el nombre del modelo y la lista de palabras de la pregunta (sus lemas en minúsculas)
		# antes: almacena la lista de palabras (que estén en el modelo) en 'syn1negs' (words) y nada más
		# ahora: expande cada palabra a la lista de entidades por las que se ha cambiado y almacena las que están en el modelo en 'syn1negs' (wordsLists)
		def __init__(self, modelname, qwords="ALL"):
			self.MVP_modelname = modelname            # MVP_modelname es el nombre del modelo gestionado por este objeto
			self.MVP_pmodel = demo.dict_models[modelname]  # MVP_pmodel es el proxy al modelo (objeto de la clase ModelTrainedProxy)

			# amplia cada word de la pregunta con todas las entityNames a las que se ha cambiado en alguna ocasión (y aquellas cuyo nombre la contiene)
			# solo se lo preguntamos a dbManagerHistorical, porque esos son los textos con los que hemos entrenado la red
			# qwordsLists es una lista de objetos, uno por cada palabra original,  del tipo {"word": word_original, "listSubstitutes": lista_sustitutos} 
			qwordsLists = [ {"word": w, "listSubstitutes": dbManagerHistorical.getEntityNamesOfSF(w)} for w in qwords]
				
			# elimina de 'qwords' aquellas palabras que no están en el modelo
			if qwords != "ALL":
				# la función 'inVocav' de un pmodel nos dice si una palabra está en el vocabulario del wmodel controlado por ese pmodel
				qwordsInModel =  list(filter(lambda w: self.MVP_pmodel.inVocab(w), qwords))
				
				# procesamos las listas de sustitutos para quitar los que no estén en el modelo
				qwordsListsInModel = [ {"word": o["word"], "listSubstitutes":  list(filter(lambda w: self.MVP_pmodel.inVocab(w), o["listSubstitutes"])) }     for o in qwordsLists]
				qwordsListsInModel =  list(filter(lambda o: len(o["listSubstitutes"]) > 0, qwordsListsInModel))  # nos cargamos los objetos con listas de sustitutos vacías
				
				if "agil" in modelname:
					print("*** qwordsLists:", qwordsLists)
					print("*** wordsListsModel:", qwordsListsInModel)
					
			# crea la variable 'syn1negs', un diccionario con dos campos:
			# 'words' (una lista de palabras -lemas- de la pregunta que existan en el modelo); y la lista 'entityProbsNearWords_List'
			# cada entrada de 'entityProbsNearWords_List' será un diccionario {"surfaceForm": name, "uri": URL, "probabilities": pb}
			# lo he ampliado con las listas de palabras, que es lo que se emplea ahora
			self.syn1negs = {"words": qwordsInModel, "entityProbsNearWords_List": [], "wordsLists": qwordsListsInModel, "entityProbsNearWordsLists_List": []}

			# crea la variable lastEntityInModel. Indica si la última entidad procesada (llamada a run()) está en el modelo
			self.lastEntityInModel = False


		# se le pasa una palabra (por ahora sólo la respuesta) y devuelve una lista con las probabilidades de TODAS las palabras del modelo
		def getVectorProbabilites(self, word):
			word = word.lower()

			try:
				# esto llama a la función __getattribute__ del pmodel, con valor attr = 'get_vector'
				# lo cual hace que se llame a la función get_vector() del wmodel de gensim, que devuelve el vector característico
				wVec = self.MVP_pmodel.get_vector(word) # esto devuelve el vector caracetrístico, sus 300 elementos

				# Matrix multiplication of syn1neg (qué es esto?) and wVec. Se supone que es el hxW'
				auxMatrix = numpy.matmul(self.MVP_pmodel.syn1neg, wVec)

				# apply softmax to the obtained vector
				probs = softmax(auxMatrix)
				
				return probs
			except Exception as e:
				app.logger.info(e)
				return []

		# devuelve el objeto  syn1negs  propio de este modelo
		def getSyn1negs(self):
			return self.syn1negs;

		#  devuelve  self.syn1negs, pero antes convierte las probabilidades de flotantes a cadenas, en el caso anterior y el actual
		def getSyn1negsStr(self):
			newReturn = self.syn1negs
			newReturn["entityProbsNearWords_List"] = list(map(lambda x: {"nameEntity": x["nameEntity"], "uri": x["uri"], "probabilities": list(map(lambda y: str(y), x["probabilities"]))} , newReturn["entityProbsNearWords_List"]))
			newReturn["entityProbsNearWordsLists_List"] = list(map(lambda x: {"nameEntity": x["nameEntity"], "uri": x["uri"], "probabilities": list(map(lambda y: str(y), x["probabilities"]))} , newReturn["entityProbsNearWordsLists_List"]))
			
			return newReturn

		# función auxiliar para sumar los números de una lista
		def sumLista (self, lista):
			suma = 0
			for f in lista:
				suma += f
			return suma
		

		# para calcular las probabilidades de una entidad en un modelo concreto. Recibe la entidad
		def run (self, entity):
			# esta es la palabra que hay que buscar en el modelo			
			nameEntity = entity["entityLowerName"]
			uriEntity = entity["@URI"]

			if self.MVP_modelname != "google":  # no se hace nada para el modelo de google
				if self.MVP_pmodel.inVocab(nameEntity):
					# name está en el vocabulario del modelo
					self.lastEntityInModel = True
					
					totalVocabVector = self.getVectorProbabilites(nameEntity)   # vector con las probabilidades (respecto a name) de todas las palabras del vocabulario del modelo
					if self.syn1negs["words"] == "ALL":
						self.syn1negs["entityProbsNearWords_List"].append({"nameEntity": nameEntity, "uri": uriEntity, "probabilities": totalVocabVector})
					else:
						# pb es el vector de probabilidades de las palabras de la pregunta, teniendo en cuenta sólo las palabras
						pb = list(map(lambda w: totalVocabVector[self.MVP_pmodel.wv.index2word.index(w)], self.syn1negs["words"]))
						self.syn1negs["entityProbsNearWords_List"].append({"nameEntity": nameEntity, "uri": uriEntity, "probabilities": pb})

						# pb2 es el vector de probabilidades de las palabras de la pregunta, teniendo en cuenta las palabras y las entidades a las que se cambien
						pb2 = [  list(map(lambda w: totalVocabVector[self.MVP_pmodel.wv.index2word.index(w)], o["listSubstitutes"]))  for o in self.syn1negs["wordsLists"]   ]
						pb2sum = [ self.sumLista(l) for l in pb2 ]
						self.syn1negs["entityProbsNearWordsLists_List"].append({"nameEntity": nameEntity, "uri": uriEntity, "probabilities": pb2sum})
				
				else:
					# name no está en el vocabulario del modelo
					self.lastEntityInModel = False

			return self

	# fin de la clase ModelVectorProbabilites
	
	
	

	# Comienza lo que se ejecuta cuando se recibe '/algorithmA2'. Hasta ahora eran definiciones de clases
	
	if request.method == 'POST':
		pText = request.values.get('fA2Text')
		pQuestion = request.values.get('fA2Question')
		pAnswer = request.values.get('fA2Answer')
		support = request.values.get('fA2Support')
		confidence = request.values.get('fA2Confidence')
		posSelected = json.loads(request.values.get('fA2Sigpos'))

		# sometemos al texto al procesado de añadirle los sufijos, como se hizo con los textos de entrenamiento
		resultado = _processContent(pText)
		sufixedText = resultado[0]
		
		# este será el resultado (campos en sec 5.9)
		result = {}
		
		# estas son las palabras relevantes de la pregunta
		# devuelve una lista de diccionarios, uno por palabra con las claves [offset, word, POS, lemma], la primera un número y el resto cadenas
		wordsInQuestionJSON = demo.getInterestingWordsInText(pQuestion, posSelected)

		# Do all queries concurrent
		# este módulo proporciona un objeto session, cuyas llamadas (get|post) son asíncronas (simplemente devuelven un gestor para consultar si han terminado)
		# la llamada gestor.result() se bloquea a la espera de su finalización
		futSes = FuturesSession()

		# el tamaño del texto+pregunta, se usa cuando pidamos identificación de entidades sobre T+P+R
		# si el offset de la sf de una entidad es mayor que este número, claramente corresponde a la respuesta
		lenCharsInTplusP = len(sufixedText+"\n"+pQuestion+"\n")  
		
		# se pide a la DB-SL el preferido para cada entidad identificada en el texto+pregunta+respuesta
		# ver sección 6.4 del documento de la arquitectura para el formato de la solicitud y la respuesta
		annotateTextRequest = futSes.get(_URL_DB_SL_annotate, params={"text": sufixedText+"\n"+pQuestion+"\n"+pAnswer, "confidence": confidence, "support": support}, headers={"Accept": "application/json"})
		
		# esto sería para pedir los candidatos para cada entidad identificada en el texto (por qué no añade pregunta y respuesta?)
		# está comentado porque no se usa
		# candidatesTextRequest = futSes.get(_URL_DB_SL + "/candidates", params={"text": t, "confidence": confidence, "support": support}, headers={"Accept": "application/json"})
		
		# se pide el preferido para la respuesta de forma aislada
		annotateAnswerRequest = futSes.get(_URL_DB_SL_annotate, params={"text": pAnswer, "confidence": confidence, "support": support}, headers={"Accept": "application/json"})
		
		# esto sería para pedir los candidatos para la respuesta aislada, está comentado porque no se usa
		# candidatesAnswerRequest = futSes.get(_URL_DB_SL + "/candidates", params={"text": r, "confidence": confidence, "support": support}, headers={ "Accept": "application/json"})
		
		# se crean objetos gestores para procesar el resultado de la DB-SL
		# estos gestores van a realizar (en scanEntities) nuevas consultas a la DBpedia para completar la información recida de la DB-SL
		# en la inicialización únicamente se crea la variable entityData = {'byUri': {}, 'byType': {}, 'byOffset': {}}
		# donde se van a almacenar todas las entidades identificadas indexadas de tres formas: por URI, por tipo y por offset
		dbManagerText = _DBManager() 
		dbManagerAnswer = _DBManager()
		
		# hasta ahora se han lanzado 2 llamadas asíncronas en paralelo, para calcular las entidades identificadas en T+P+R y la correspondiente a R en solitario
		# ahora se espera por la conclusión de la primera
		dbslText_Json = annotateTextRequest.result().json()

		# ahora se espera por la conclusión de la otra,
		dbslOnlyAnswer_Json = annotateAnswerRequest.result().json()
				

		# llamadas para esperar por las solicitudes de candidatos, que actualmente no se realizan
		# result["dbpedia_text_candidates"] = candidatesTextRequest.result().json()   # comentado porque no se usa
		# result["dbpedia_answer_candidates"] = candidatesAnswerRequest.result().json()   # comentado porque no se usa
		

		# se le pasan a los gestores los preferidos recibidos de la DB-SL, donde se completan con nuevas consultas a la DBpedia
		dbManagerText.scanEntities(dbslText_Json)          # A2.1, ahora, los datos de la fase 1 del algoritmo están en dbManagerText.entityData
		dbManagerAnswer.scanEntities(dbslOnlyAnswer_Json) 
		
		# ahora vamos a elegir la entidad que usamos para la respuesta, si la calculada aislada o la calculada tras el texto

		# lo siguiente son listas de entidades, pero sólo puede contener una a lo sumo, la entidad detectada sobre la respuesta, ya sea en solitario o añadida al T+P
		answerEntitiesWithText = dbManagerText.getEntitiesAfterOffset(lenCharsInTplusP)  # lenCharsInTplusP = longitud(texto + P)
		answerEntitiesAlone = dbManagerAnswer.getEntitiesAfterOffset(0) 
		
		# si ninguna de las dos contiene nada, no se puede continuar, y se responde con un error
		if len(answerEntitiesWithText) == 0 and len(answerEntitiesAlone) == 0:
			result["error"] = "No entities identified for answer"
			return jsonify(result)
				
		result["answerEntityWithText"] = answerEntitiesWithText
		result["answerEntityAlone"] = answerEntitiesAlone
		
		# priorizamos la entidad obtenida al añadir P+R al final de T, y la ponemos por defecto
		result["answerUsed"] = "WithText"  # un flag para saber cuál se seleccionó: inicialmente, la derivada de la respuesta puesta al final del texto
		answerEntities = answerEntitiesWithText
		
		# si la lista de la respuesta tras T+P está vacía (no se encontró la R añadiéndola a T+P), usaremos la entidad de R identificada en solitario
		if len(answerEntitiesWithText) == 0: 
			# esta será la lista de entidades gestionadas por dbManagerAnswer, que se supone que sólo es una
			answerEntities = answerEntitiesAlone
			result["answerUsed"] = "OnlyAnswer" # un flag para saber cuál se seleccionó: la derivada de la respuesta en solitario
		
		# ya se ha anotado en result["answerUsed"] si se usa 'WithText' o 'OnlyAnswer'
		
		
		# answerEntities debería contener un único elemento, la entidad correspondiente a R
		entityAnswer = answerEntities[0]   # nos quedamos con el único elemento de la lista de entidades de la respuesta
		print("\nLa entidad de la respuesta es", entityAnswer["@URI"], entityAnswer["entityName"])
		
		result["significativeEntities"] = [] # se inicializa una lista vacía en el resultado para almacenar los candidatos finalmente seleccionados
				
				
		# A2.2, ahora, los datos de la fase 2 del algoritmo están en entityAnswer
			
		result["answerSparqlTypes"] = entityAnswer["sparqlTypes"]   
		result["answerWikicats"] = entityAnswer["wikicats"]

		excludeTypes = {"Agent", "Thing"} # set de tipos que hay que excluir de los tipos de la respuesta por ser muy genéricos

		# los tipos de R van a ser los combinedTypes (union de los de DB_SL y SPARQL) menos los que hay que excluir
		typesAnswer = list(set(entityAnswer["combinedTypes"]) - excludeTypes)
		
		# una lista para guardar los subjects de R
		# cada elemento es un diccionario, con keys 'value' (la parte final del subject tras el ':') y 'words' (la lista de palabras del subject, que están unidas por '_')
		subjectsAnswer = []
		
		# analizamos cada subject de la respuesta, es una cadena del tipo   'http://dbpedia.org/resource/Category:5th-century_BC_rulers'
		for s in entityAnswer["subjects"]:
			category = s.split(":")[2]  # nos quedamos con lo que va después del segundo ':'   5th-century_BC_rulers
			subjectsAnswer.append({"value": s, "words": category.split("_")})   # separamos las palabras que están unidas por '_'
		
		# set de subjects completos de la respuesta
		# e.j., {'http://dbpedia.org/resource/Category:Achaemenid_kings', 'http://dbpedia.org/resource/Category:Twenty-seventh_Dynasty_of_Egypt', ...}
		set_subjects_answer =  set(entityAnswer["subjects"])

		# set de subjects de la respuesta, tras quitarle a cada subject la primera palabra
		# para el ejemplo anterior, {'kings', 'Dynasty_of_Egypt', ...}
		set_subjectsWithoutFirstWord_answer = set(["_".join(x["words"][1:]) for x in subjectsAnswer])  
		
		# generada la información sobre candidatos y R (typesAnswer, subjectsAnswer, set_subjects_answer, set_subjectsWithoutFirstWord_answer)
		
		
		historicalDictionaries = dbManagerHistorical.getDictionaries()

		wordsInQuestion = list(map(lambda x: x["word"], wordsInQuestionJSON))
		print("*** wordsInQuestion:", wordsInQuestion)
		lemmasInQuestion = list(map(lambda x: x["lemma"].lower(), wordsInQuestionJSON))
		print("*** lemmasInQuestion:", lemmasInQuestion)
		
		
		# crea un objeto answerAllModelsVectorProbabilities del tipo AllModelsVectorProbabilities, para calcular las probabilidades de la respuesta
		# ese objeto tiene una variable 'listModelVectorProbabilities' que es una lista de objetos {name:str, model:ModelVectorProbabilites}
		# le pasa una lista de palabras, los lemas de las palabras significativas de la pregunta (strings)
		# no se calcula nada, sólo se crean los objetos ModelVectorProbabilites para cada modelo
		answerAllModelsVectorProbabilities = AllModelsVectorProbabilities(lemmasInQuestion)
		# crea un nuevo objeto para el Text, con las mismas palabras que el de Answer
		textAllModelsVectorProbabilities   = AllModelsVectorProbabilities(lemmasInQuestion)
		
		# calcula las probabilidades de la respuesta en todos los modelos, le pasa un diccionario con la sf de la respuesta y el URI de su entidad
		# esto calcula el vector de probabilidades (de todos los modelos), de la respuesta
		# answerAllModelsVectorProbabilities.run({"@surfaceForm": r, "@URI": entityAnswer["@URI"]}) # por qué no le pasamos entityAnswer????
		answerAllModelsVectorProbabilities.run(entityAnswer)
		
		# valores de la matriz de entrenamiento (vectores significativos?)
		print("\n", "answerAllModelsVectorProbabilities.getSyn1negs() =", answerAllModelsVectorProbabilities.getSyn1negs())    
		


		# lista de URLs seleccionadas. No se devuelve, es sólo para no repetir
		# pongo inicialmente la URL de R, y así ya nunca la devuelvo
		addedUris = [entityAnswer["@URI"]]

		result["rejectedTerms"] = []  # lista para anotar los candidatos descartados y su motivo: items = diccionario con 'Resource' y 'Reason'
		AnswerIsPerson = False
		
		
		byTypeHistorical = historicalDictionaries['byType']
		
		# primero compara R con las entidades de los textos de entrenamiento
		# me parece una aproximación mejorable, bucle tiposRespuesta x entidadesHISTORICAS
		for tAnswer in typesAnswer:  # estudiamos cada tipo de R
			# From the training texts
			if tAnswer in byTypeHistorical:  # si este tipo no está en la lista de tipos de los textos de entrenamiento, pasamos
				for entity in byTypeHistorical[tAnswer]:  # estudiamos cada entidad E de los textos de entrenamiento con este tipo
					if entity['@URI'] in addedUris: # si esta entidad ya está en la LISTA, la descartamos
						result["rejectedTerms"].append({'Resource': entity["@URI"], 'Reason': "Already selected"})
					else:
						set_subjects_entity =  set(entity["subjects"])
						commonSubjects = list(set_subjects_entity & set_subjects_answer)  # lista de subjects comunes a E y R
						
						_subjects = []  # construimos la lista de subjects de E
						for s in entity["subjects"]:
							category = s.split(":")[2]
							_subjects.append({"value": s, "words": category.split("_")})

						partialCommonSubjects = []  # lista de subjects comunes excepto en la primera palabra  (MEJORAR la definición de match parcial)
						
						# si hay subjects comunes, ya no miramos las coincidencias parciales
						if len(commonSubjects) == 0:
							set_subjectsWithoutFirstWord_entity = set(["_".join(x["words"][1:]) for x in _subjects])
							partialCommonSubjects = list(set_subjectsWithoutFirstWord_entity & set_subjectsWithoutFirstWord_answer)

						# si no comparten subjects (total o parcialmente), la descartamos
						if len(commonSubjects) + len(partialCommonSubjects) == 0:
							result["rejectedTerms"].append({'Resource': entity["@URI"], 'Reason': "Don't share subjects"})
						elif tAnswer == "Person":
								AnswerIsPerson = True
								# comprobamos si cumple con los requisitos para Person  ('in' busca una cadena en otra entity["rawSparqlTypes"])
								if not "http://dbpedia.org/ontology/Person" in entity["rawSparqlTypes"]:
									result["rejectedTerms"].append({'Resource': entity["@URI"], 'Reason': "not a DBpedia PERSON"})
								elif not "http://dbpedia.org/class/yago/Person" in entity["rawSparqlTypes"]:
									result["rejectedTerms"].append({'Resource': entity["@URI"], 'Reason': "not a Yago PERSON"})
								elif  len(entity["personProperties"]) == 0:
									result["rejectedTerms"].append({'Resource': entity["@URI"], 'Reason': "no PERSON properties"})
								else:
									addedUris.append(entity['@URI']) # la añadimos a la lista de seleccionadas
									result["significativeEntities"].append(entity)
									textAllModelsVectorProbabilities.run(entity)  # PROB
									for m in textAllModelsVectorProbabilities.getModelsNotHaveLastWord():
										result["rejectedTerms"].append({'Resource': entity["@surfaceForm"], 'Reason': "Does not exist in model " + m})

						# no es Person
						else:
							addedUris.append(entity['@URI'])  # la añadimos a la lista de seleccionadas
							result["significativeEntities"].append(entity)
							textAllModelsVectorProbabilities.run(entity) # PROB
							for m in textAllModelsVectorProbabilities.getModelsNotHaveLastWord():
								result["rejectedTerms"].append({'Resource': entity["@surfaceForm"], 'Reason': "Does not exist in model " + m})
							
						


		""" # comentado por no acabar de verle el fundamento
		# ahora vemos todas las entidades de los textos de entrenamiento  OTRA VEZ???
		# Also add all entities that share any word with the answer in type or wikicat
		for eUri in historicalDBpediaDataMod['byUri']:	# todas las URIs de byUri
			# si la actual ya la hemos añadido, pasamos
			if eUri not in addedUris:
				entity = historicalDBpediaDataMod['byUri'][eUri][0]  # le añadí el [0] para coger solo la primera, ya que sólo hay una
				# Check if any wikicat, type or sparqlType shares any word with answer
				# es una lista de un único elemento, por qué esta, por que no la seleccionada?????
				wordsAnswer = list(map(lambda x: x["@surfaceForm"].lower(), dbslOnlyAnswer_Json["Resources"]))  
				# es una lista de un único elemento

				for w in wordsAnswer:
					# si la respuesta forma parte de algún tipo (original o sparql) o está en alguna wikicat, también nos vale ?????????
					if w in entity["@types"].lower() or any( (w in x.lower()) for x in entity["sparqlTypes"]) or any( (w in x.lower()) for x in entity["wikicats"]):
						addedUris.append(entity['@URI'])  # la añadimos a la lista de seleccionadas
						result["significativeEntities"].append(entity)
						textAllModelsVectorProbabilities.run(entity)
						for m in textAllModelsVectorProbabilities.getModelsNotHaveLastWord():
							result["rejectedTerms"].append({'Resource': entity["@surfaceForm"], 'Reason': "Does not exist in model " + m})
						break;
		"""
		
		print("%%% candidatos de los históricos", len(result["significativeEntities"]))
		
		checkDuplicates = []
		textNoRepEntities = []   # esta será la lista de entidades del texto, aun sin filtrar, solo se han quitado las repes

		# ahora lo mismo que antes para las entidades del texto T
		
		textDictionaries = dbManagerText.getDictionaries()
		
		textEntitiesLists = list(dbManagerText.getByUri().values())  # lista de listas
		textEntities = [item for sublist in textEntitiesLists for item in sublist] # lista plana con todos los anteriores elementos
		
		# las textEntities no han pasado por el preprocesamiento, pero le hemos añadido los sufijos antes de annotate
		
		for entity in textEntities:
			# @URI/@surfaceForm no puede repetirse (puede pasar, ya que no ha pasado por el preprocesamiento)
			# UNIFICAR con los textos HISTÓRICOS, deben compartir nombres
			if entity["@URI"]+"/"+entity["@surfaceForm"] in checkDuplicates and (int(entity["@offset"]) < lenCharsInTplusP):
				result["rejectedTerms"].append({'Resource': entity["@URI"], 'Reason': "Duplicated"})
				continue
			
			checkDuplicates.append(entity["@URI"]+"/"+entity["@surfaceForm"])
			textNoRepEntities.append(entity)  # puede entrar varias veces con distinta sf
			
			_subjects = [] # construimos la lista de subjects de E
			for s in entity["subjects"]:
				category = s.split(":")[2]
				_subjects.append({"value": s, "words": category.split("_")})

			# Compare subjects
			set_subjects_entity =  set(entity["subjects"])
			commonSubjects = list(set_subjects_entity & set_subjects_answer)  # lista de subjects comunes a E y R

			partialCommonSubjects = []  # lista de subjects comunes excepto en la primera palabra  (MEJORAR la definición de match parcial)
			
			# si hay subjects comunes, ya no miramos las coincidencias parciales
			if len(commonSubjects) == 0:
				set_subjectsWithoutFirstWord_entity = set(["_".join(x["words"][1:]) for x in _subjects])
				partialCommonSubjects = list(set_subjectsWithoutFirstWord_entity & set_subjectsWithoutFirstWord_answer)


			# por qué dbslOnlyAnswer_Json?? por qué no la seleccionada
			# urisAnswer = list(map(lambda x: x["@URI"], dbslOnlyAnswer_Json["Resources"]))  # lista de longitud 1
			urisAnswer = [entityAnswer["@URI"]]
			
			if entity["@URI"] ==  entityAnswer["@URI"]:
				result["rejectedTerms"].append({'Resource': entity["@URI"], 'Reason': "Same resource answer"})
			elif entity['@URI'] in addedUris:
				result["rejectedTerms"].append({'Resource': entity["@URI"], 'Reason': "Already selected"})
			elif not any((x in typesAnswer) for x in entity["combinedTypes"]):
				result["rejectedTerms"].append({'Resource': entity["@URI"], 'Reason': "Don't share types with answer"})
			elif (len(commonSubjects) + len(partialCommonSubjects)) == 0:
				result["rejectedTerms"].append({'Resource': entity["@URI"], 'Reason': "Don't share subjects"})
			elif AnswerIsPerson:
				if not "http://dbpedia.org/ontology/Person" in entity["rawSparqlTypes"]:
					result["rejectedTerms"].append({'Resource': entity["@URI"], 'Reason': "PERSON without DBpedia type person"})
				elif not "http://dbpedia.org/class/yago/Person" in entity["rawSparqlTypes"]:
					result["rejectedTerms"].append({'Resource': entity["@URI"], 'Reason': "PERSON without YAGO type person"})
				elif len(entity["personProperties"]) == 0:
					result["rejectedTerms"].append({'Resource': entity["@URI"], 'Reason': "PERSON without person properties"})
				else:
					result["significativeEntities"].append(entity)
					textAllModelsVectorProbabilities.run(entity)
					for m in textAllModelsVectorProbabilities.getModelsNotHaveLastWord():
						result["rejectedTerms"].append({'Resource': entity["@surfaceForm"], 'Reason': "Does not exist in model " + m})
						
			else:
				result["significativeEntities"].append(entity)
				textAllModelsVectorProbabilities.run(entity)
				for m in textAllModelsVectorProbabilities.getModelsNotHaveLastWord():
						result["rejectedTerms"].append({'Resource': entity["@surfaceForm"], 'Reason': "Does not exist in model " + m})
			
			
		print("%%% candidatos tras procesar el texto", len(result["significativeEntities"]))
		result["dbpedia_text"] = dbslText_Json 
		result["dbpedia_text"]["Resources"] = textNoRepEntities

		result["wordsInQuestion"] = wordsInQuestionJSON;




		#Pk in model
		values = {}    # resultados, dict con clave nombre y valor syn1negs
		
		# procesamos todas las entidades para las cuales se han calculado las probabilidades
		# cada m es {'name':modelname, 'syn1negs': syn1negs del MVP}
		for m in textAllModelsVectorProbabilities.getSyn1negs():
			print("procesando modelo ",m["name"])
			uri = entityAnswer["@URI"]
			answerLowerName = entityAnswer["entityLowerName"]
			values[m["name"]] = []
							
			# comprobamos que la respuesta esté en el vocabulario de este modelo
			if not demo.dict_models[m["name"]].inVocab(answerLowerName):
				print("La respuesta no está en el modelo ", m["name"])
				values[m["name"]].append({"error": "La respuesta no está en el modelo"})
				continue
			
			# cogemos las probabilidades de la respuesta
			answerMVP = answerAllModelsVectorProbabilities.getMVP(m["name"])
			answerSyn1negs = answerMVP.getSyn1negs()

			# comprobaos que haya probabilidades para alguna palabra de la pregunta
			if len(answerSyn1negs["entityProbsNearWordsLists_List"]) > 0:
				answerVector = numpy.array(answerSyn1negs["entityProbsNearWordsLists_List"][0]["probabilities"])
				applyFactor = False
				minVectorA = numpy.repeat(1e-10, len(answerVector)) # vector con los valores igual al mínimo 1e-10
				if any(numpy.less(answerVector, minVectorA)):  # cierto si algún componente del vector answerVector es menor que el mínimo
					answerVector = numpy.multiply(answerVector, 1000000)  # si pasa eso, múltiplicamos todos los componentes del vector por el factor un millon
					applyFactor = True  # recordar que le hemos aplicado el factor a la respuesta

				for entityProbs in m["syn1negs"]["entityProbsNearWordsLists_List"]:  # para hacerlo con words --> entityProbsNearWords_List
					entityVector = numpy.array(entityProbs["probabilities"])
					minVectorE = numpy.repeat(1e-10, len(entityVector))
					
					_answerVector = answerVector
					if applyFactor:
						entityVector = numpy.multiply(entityVector, 1000000)  # si le habíamos aplicado el factor a la respuesta, también lo hacemos a esta entidad
					elif any(numpy.less(entityVector, minVectorE)):
						entityVector = numpy.multiply(entityVector, 1000000)
						_answerVector = numpy.multiply(_answerVector, 1000000)  # si no se lo habiamos aplicado a la respuesta, se lo aplicamos ahora si el entityVector lo requiere

					# print("\nanswer = ", _answerVector )
					# print("entity = ", entityVector)
					
					similarity = numpy.subtract(numpy.float32(1.0), cosine(_answerVector, entityVector))
					values[m["name"]].append({"nameEntity": entityProbs["nameEntity"], "URI": entityProbs["uri"], "Cosine similarity with answer": str(similarity)})
			
			# no hay probabilidades para ninguna palabra de la pregunta
			else:
				print("No ha probabilidades para ninguna palabra de la pregunta en el modelo ", m["name"])
				values[m["name"]].append({"error": "No ha probabilidades para ninguna palabra de la pregunta"})
				continue

		result["similarities"] = values
		# answerAllModelsVectorProbabilities.getSyn1negsStr() es un diccionario con clave nombre M y valor M.getSyn1negs()
		result["probabilities"] = {"answer": answerAllModelsVectorProbabilities.getSyn1negsStr(), "candidates": textAllModelsVectorProbabilities.getSyn1negsStr()}

		try:
			return jsonify(result)
		except Exception as e:
			app.logger.error(e) 
			return jsonify({})
	return jsonify({})


# esto se usa???
# def getVectorProbabilites(modelname, word):
# 	_pmodel = demo.dict_models[modelname]
# 
# 	word = word.lower()
# 
# 	try:
# 		wVec = _pmodel.get_vector(word)
# 
# 		#Matrix multiplication of syn1neg and wVec
# 		probs = numpy.matmul(_pmodel.syn1neg, wVec)
# 
# 		#apply softmax to the obtained vector
# 		return softmax(probs)
# 	except Exception as e:
# 		app.logger.error(e)
# 		return []


# Arranca el servidor HTTP escuchando en el puerto 5000

if __name__ == '__main__':
	app.run(debug=True, host='0.0.0.0', threaded=True)

# por qué se imprimen los nombres de los modelos la segunda vez, tras arrancar el servidor