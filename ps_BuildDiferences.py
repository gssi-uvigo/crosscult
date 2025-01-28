#!/Library/Frameworks/Python.framework/Versions/Current/bin/python3

# Este programa coge varios directorios donde hay ficheros '.s' y sus correspondientes '.p', que responden a diferentes valores de confidence
# compara las ganancias y pérdidas de entidades respecto a la versión con 0.5 y las anota en ficheros
# input: el directorio raíz donde están los directorios con cada versión de los ficheros
# output: escribe en cada directorio el fichero con las diferencias respecto a la versión de referencia




import os
import pickle
import requests
from requests.utils import quote
from requests_futures.sessions import FuturesSession
import json
import sys

from px_aux import saveFile as _saveFile

# funciones



# para detectar las entidades que se pieden o se gana de un fichero a otro
# la inicial 'r' es la del directorio de refencia
# la inicial 't' es la del directorio target, cuyas variaciones respecto al de refencia queremos estudiar
def findDiffEntities (sfilename, rdir, tdir):
		
	rpfilename = rdir+"/"+sfilename+".p"
	tpfilename = tdir+"/"+sfilename+".p"
	
	rpfile = open(rpfilename, 'rb') 
	tpfile = open(tpfilename, 'rb') 
	
	rdics = pickle.load(rpfile)
	tdics = pickle.load(tpfile)
	
	rdicOffsets = rdics["byOffset"]
	tdicOffsets = tdics["byOffset"]
	
	# obtenemos sendas listas con los offsets, las claves de los diccionarios
	roffsets = list(rdicOffsets)  
	toffsets = list(tdicOffsets)
	
	# listas de offsets perdidos y ganados en el nuevo fichero.p
	offsetsPerdidos = set(roffsets) - set(toffsets)
	offsetsGanados = set(toffsets) - set(roffsets)
	
	newEntiyOffsetsP = {}
	for o in offsetsPerdidos:
		entity = rdicOffsets[o]
		newEntiyOffsetsP[o] = entity
	
	newEntiyOffsetsG = {}
	for o in offsetsGanados:
		entity = tdicOffsets[o]
		newEntiyOffsetsG[o] = entity
	
	finalResultP = {'byUri': {}, 'byType': {}, 'byOffset': newEntiyOffsetsP}
	finalResultG = {'byUri': {}, 'byType': {}, 'byOffset': newEntiyOffsetsG}
	
	return 	(finalResultP, finalResultG)

# fin del procesamiento de un fichero



# para marcar en un '.s' las entidades existentes en un '.p'
def markEntitiesInContent (content, dicOffsetP, dicOffsetG):
	
	for o in dicOffsetP:
		entity = dicOffsetP[o]
		entity["color"] = "red"
		dicOffsetP[o] = entity
	
	for o in dicOffsetG:
		entity = dicOffsetG[o]
		entity["color"] = "green"
		dicOffsetG[o] = entity	
		
	dicOffsetP.update(dicOffsetG)
	
	listOffsets = list(dicOffsetP)
	
	listIntOffsets = sorted(map(lambda x: int(x), listOffsets))
	
	finalHTMLContent = ""
	
	currentPosition = 0
	
	for o in  listIntOffsets:
		entity = dicOffsetP[str(o)]
		text = content[currentPosition:o]
		currentPosition += len(text)
		
		finalHTMLContent += text.replace("\n", "\n<p>")
		
		sf = entity["@surfaceForm"]				
		urlEntity = entity["@URI"]
		color = entity["color"]
		
		finalHTMLContent += "<a style='color: "+color+"' href='"+urlEntity+"'>"+sf+"</a>"

		currentPosition += len(sf)
	
	return finalHTMLContent

# fin de funciones






# al menos debe haber un parámetro
if len(sys.argv) < 2:
	print("Usa: "+sys.argv[0]+" directorio")
	exit(-1)
	
# si hay un parámetro, no puede empezar por '-'y debe ser un directorio
if len(sys.argv) == 2:
	origin = sys.argv[1]
	if not os.path.isdir(origin):
		print(sys.argv[0]+" no es un directorio")
		exit(-1)

		
# comienza el procesado

dirRef = "0.5"
dirList = ["0.6", "0.7", "0.8", "0.9", "0.95"]

print("Procesando directorio "+origin+"...")
numFiles = 0
for sfilename in sorted(os.listdir(origin)):
	if not sfilename.endswith(".s"):
		continue
	else:
		numFiles += 1
		sfullfilename = origin+"/"+sfilename
		print(numFiles, " **************** Procesando fichero ", sfullfilename+"...\n")
		for dir in dirList:
			refDir = origin+"/"+dirRef
			targetDir = origin+"/"+dir
			(diffEntitiesLost, diffEntitiesWon) = findDiffEntities(sfilename, refDir, targetDir)
			
			pDiffsFilename = targetDir+"/"+sfilename+".p.diffs"+dirRef+".p.html"
			print(pDiffsFilename)
			
			sfile = open(sfullfilename, 'r')
			content = sfile.read()
	
			highlightedContent = markEntitiesInContent(content, diffEntitiesLost["byOffset"], diffEntitiesWon["byOffset"])
			_saveFile(pDiffsFilename, highlightedContent)
	

	

	
	
	
	