import os
import requests
import re
import time
import pickle
from flask import request, jsonify
from os.path import isfile
from requests_futures.sessions import FuturesSession



# atiende la solicitud para pedir la distancia entre dos palabras de un modelo
# devuelve un objeto con varias claves: distance, similarity, mostSimilarW1, mostProbableW1, mostSimilarW2, mostProbableW2
def getDistance():
	from pp_app import demo as _demo
	
	w1 = request.values.get('word1')
	w2 = request.values.get('word2')
	modelName = request.values.get("modelName")

	if not modelName:
		result["error"] = "The model does not exist"
		return jsonify(result)

	result = {}

	if not w1 or not _demo.dict_models[modelName].inVocab(w1):
		result["error"] = "Word 1 does not exist in the vocabulary."
		return jsonify(result)
	if not w2 or not _demo.dict_models[modelName].inVocab(w2):
		result["error"] = "Word 2 does not exist in the vocabulary."
		return jsonify(result)

	result["distance"] = str(_demo.dict_models[modelName].distance(w1, w2))
	result["similarity"] = str(_demo.dict_models[modelName].similarity(w1, w2))

	result["mostSimilarW1"] = _demo.dict_models[modelName].similar_by_word(w1,20)
	result["mostSimilarW2"] = _demo.dict_models[modelName].similar_by_word(w2,20)

	result["mostProbableW1"] = []
	for p in _demo.dict_models[modelName].predict_output_word([w1]):
		if (p[1] >= 0.05):
			result["mostProbableW1"].append([p[0], str(p[1])])
	
	result["mostProbableW2"] = []
	for p in _demo.dict_models[modelName].predict_output_word([w2]):
		if (p[1] >= 0.05):
			result["mostProbableW2"].append([p[0], str(p[1])])

	return jsonify(result)
	

#############################################################################################################################################


# atiende la solicitud para pedir el vocabulario de un modelo
def getVocabModel():
	from pp_app import app as _app, demo as _demo
	
	if request.method == "GET":
		modelname = request.values.get('modelName')
		_app.logger.info(modelname)
		if modelname in _demo.dict_models and modelname != "google":
			_pmodel = _demo.dict_models[modelname]
			# app.logger.info(dir(_pmodel.rawVocab))    # dir(o) = lista de atributos válidos del objeto o
			return jsonify(list(_pmodel.rawVocab.keys()))

	return jsonify({})

#############################################################################################################################################

# atiende la solicitud para pedir las n (parámetro) palabras más similares a una dada (parámetro) en un modelo (parámetro)
# devuelve un objeto con la clave 'mostSimilarWords', una lista de listas (cada una de dos elementos: la palabra y la similitud)
def getSimilarWords():
	from pp_app import demo as _demo, historicalDBpediaDataMod as _historicalDBpediaDataMod
	
	word = request.values.get('word')
	n = request.values.get('n')
	modelName = request.values.get("modelName")
	if not modelName:
		result["error"] = "The model does not exist"
		return jsonify(result)

	result = {}
	if not word or not _demo.dict_models[modelName].inVocab(word):
			result["error"] = "Word does not exist in the vocabulary."
			return jsonify(result)
	
	similarWords = _demo.dict_models[modelName].similar_by_word(word,int(n))
	result["mostSimilarWords"] = similarWords
	
	entityWord = searchEntity(word, _historicalDBpediaDataMod)
	mostSimilarEntities = []
	mostSimilarSameTypeEntities = []
			
	if entityWord != None:
		for item in result["mostSimilarWords"]:
			w = item[0]
			e = searchEntity(w, _historicalDBpediaDataMod)
			if e != None:
				mostSimilarEntities.append(item)
				if shareTypes(entityWord,e):
					mostSimilarSameTypeEntities.append(item)
		
		result["mostSimilarEntities"] = mostSimilarEntities
		result["mostSimilarSameTypeEntities"] = mostSimilarSameTypeEntities
	
	return jsonify(result)

# para buscar una entidad en el diccionario byUri cuyo nombre en minúsculas sea el recibido como primer parámetro
def searchEntity (word, dicts_entities):
	dictByUri = dicts_entities["byUri"]
	
	for u in dictByUri:
		entity = dictByUri[u][0]
		entityLowerName = entity["entityLowerName"]
		if word == entityLowerName:
			return entity
	
	return None

# para ver si dos entidades comparten tipo
def shareTypes(e1,e2):
	ste1 = set(e1["combinedTypes"])
	ste2 = set(e2["combinedTypes"])
	
	if len(ste1 & ste2) > 0:
		return True
	else:
		return False

#############################################################################################################################################

# atiende la solicitud para almacenar la lista de Q|A
# recibe una lista de Q|A para almacenarlas en el fichero storedQA.p
def setStoredQA():
	if request.method == "POST":
		print(request.values)
		QAsString = request.values.get("value")
		listQATuplas = re.findall("(.*)\|(.*)", QAsString)
		pickle.dump(listQATuplas, open( "storedQA.p", "wb" ))
		return jsonify(listQATuplas);

#############################################################################################################################################

# atiende la solicitud para pedir los textos de entrenamiento
# busca los textos ".txt" en el directorio TEXTS_FOLDER ("./texts")
# devuelve un objeto con un campo por fichero (la clave es su nombre)
# el valor del campo es un objeto con dos campos: 'text' (el texto) y 'data' (siempre las entidades de historical_modify.txt.p)
# TAREA: no devolver siempre historical_modify.txt.p, sino que para cada f.txt buscar f.txt.p y devolverlos juntos
def getTrainingTexts():
	from pp_app import  historicalDBpediaDataMod as _historicalDBpediaDataMod
	from px_aux import 	TEXTS_FOLDER as _TEXTS_FOLDER, DEFAULT_TRAINING_TEXTS as _DEFAULT_TRAINING_TEXTS
	
	result = {}
	for f in os.listdir(_TEXTS_FOLDER):
		#if f.endswith("w"):
		if f == _DEFAULT_TRAINING_TEXTS:
			with open(_TEXTS_FOLDER+"/"+f, "rt", encoding='utf8') as content_file:
				content = content_file.read()
				content_file.close()
			result[f] = {'text': content, 'data': _historicalDBpediaDataMod}

	return jsonify(result)

#############################################################################################################################################

# atiende la solicitud para devolver los nombres de los ficheros involucrados en el entrenamiento
def getProcessingStep123Files():
	from px_aux import ORIGINAL_TEXTS_FOLDER as _ORIGINAL_TEXTS_FOLDER
		
	result = {}
	files = os.listdir(_ORIGINAL_TEXTS_FOLDER)   
	for filename in files:   
		if not filename.endswith(".txt"):
			continue
		else:
			existsNR = os.path.isfile(_ORIGINAL_TEXTS_FOLDER+"/"+filename+".s.nr.html")
			if existsNR:
				nrfile = filename+'.s.nr.html'
			else:
				nrfile = ""
				
			result[filename] = {'ofile': filename, 'sfile': filename+'.s', 'shfile': filename+'.s.html', 'nrfile': nrfile, 'phfile': filename+'.s.p.html', 'wfile': filename+'.s.w.html'} 
	
	return jsonify(result)

#############################################################################################################################################

# atiende la solicitud para devolver un fichero de texto
def getFile():
	from px_aux import ORIGINAL_TEXTS_FOLDER as _ORIGINAL_TEXTS_FOLDER
	
	fich = request.values.get('file')
	content_file =  open(_ORIGINAL_TEXTS_FOLDER+"/"+fich, "rt", encoding='utf8')
	content = content_file.read()
	content_file.close()
	
	if fich.endswith(".txt"):
		head = fich+": fichero original"
	elif fich.endswith(".s.html"):
		head = fich+": fichero donde se han añadido sufijos romanos a partir del contexto (<span style='color: green'>marcados en verde</span>)"
	elif fich.endswith(".s.nr.html"):
		head = fich+": informe sobre las surface forms (<span style='color: red'>marcadas en rojo</span>) a las que se estudió añadir un sufijo romano y finalmente se descartó"
	elif fich.endswith(".s"):
		head = fich+": fichero de partida, donde ya se han añadido sufijos romanos a partir del contexto"
	elif fich.endswith(".p.html"):
		head = fich+": fichero de partida, donde se han marcado las entidades detectadas"
	elif fich.endswith(".w.html"):
		head = fich+": fichero donde se han realizado las transformaciones de la surface form (<span style='color: blue'>en azul tachado</span>) a la última parte del URL de la entidad que le corresponde (<span style='color: green'>en verde</span>)"
	else:
		head = fich+": fichero con propósito desconocido"
		
	if fich.endswith(".txt")  or fich.endswith(".s"):
		content = content.replace("\n", "<p>")
		
	result = {'head':head, 'text':content}
	return jsonify(result)

#############################################################################################################################################

# atiende la solicitud para recalcular los ficheros de entidades de la DBpedia identificados en cada fichero original
def recalculateEntities():
	from px_aux import ORIGINAL_TEXTS_FOLDER as _ORIGINAL_TEXTS_FOLDER, SCRIPT_STEP2 as _SCRIPT_STEP2, SCRIPT_STEP3 as _SCRIPT_STEP3
	
	conf = request.values.get('confidence')
	sup = request.values.get('support')

	print("recalculando con ", conf, sup)
	
	res = os.system(_SCRIPT_STEP2+" -c "+conf+" -s "+sup+" "+ _ORIGINAL_TEXTS_FOLDER)
	if res != 0:
		result = {'result':'Problema con '+_SCRIPT_STEP2}
		return jsonify(result)
	else:
		res = os.system(_SCRIPT_STEP3+" "+_ORIGINAL_TEXTS_FOLDER)
		if res != 0:
			result = {'result':'Problema con '+_SCRIPT_STEP3}
			return jsonify(result)
		
	result = {'result':res}
	return jsonify(result)


#############################################################################################################################################

# esto ya no se usa, ahora se genera en ps_2 el *.p.html con el mismo resultado, que se entrega vía getFile
# atiende la solicitud para devolver un fichero de entidades

def getEntityFile():
	from px_aux import ORIGINAL_TEXTS_FOLDER as _ORIGINAL_TEXTS_FOLDER
		
	fich = request.values.get('file')
	sfile = _ORIGINAL_TEXTS_FOLDER+"/"+fich
	pfile = sfile+".p"
	
	content_file =  open(sfile, "rt", encoding='utf8')
	content = content_file.read()
	content_file.close()
	
	fileDataMod = pickle.load(open(pfile, "rb" ))
	
	result = {'text':content, 'data':fileDataMod}
	return jsonify(result)