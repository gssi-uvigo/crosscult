#!/Library/Frameworks/Python.framework/Versions/Current/bin/python3


import re
import os, os.path
import sys
import pickle


	
	

def createReport (pfilename):
	
	pfile = open(pfilename, 'rb')
	dicsEntities = pickle.load(pfile)
	byUri = dicsEntities["byUri"]
	byType = dicsEntities["byUri"]
	byOffset = dicsEntities["byOffset"]

	byuriplana = [item for sublist in byUri.values() for item in sublist]
	
	for e1 in byuriplana:
		url = e1["@URI"]
	
		if "Persian" in e1["@surfaceForm"]:
			print(e1["@surfaceForm"], "-->", e1["@URI"], e1["times"])
	
	




# si hay exactamente un parámetro, ok 
if len(sys.argv) == 2:
	origin = sys.argv[1]
# si no hay exactamente un parámetro, mal
else:
	print("Usa: "+sys.argv[0]+" fichero|directorio")
	exit(-1)


createReport(sys.argv[1])

	


	
