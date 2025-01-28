#!/Library/Frameworks/Python.framework/Versions/Current/bin/python3


import re
import os, os.path
import sys
import pickle


	
	
# para aplicarle todo el procesamiento a un fichero (se supone que '.s') y guardar el resultado como fichero.w
def createReport (pfilename):
	
	pfile = open(pfilename, 'rb')
	dicsEntities = pickle.load(pfile)
	byUri = dicsEntities["byUri"]
	byType = dicsEntities["byUri"]
	byOffset = dicsEntities["byOffset"]

	sfs = {}
	
	print("Entities que provienen de varias surface forms distintas")
	for url in byUri:
		entityList = byUri[url]
		if len(entityList) > 1:
			print("\nURL=", url.split("/")[-1], " -->", end=' ')
			for entity in entityList:
				sf = entity["@surfaceForm"]
				times = entity["times"]
				print(sf, "(", times, ")", ",", end='')
				
				if sf not in sfs:
					sfs[sf] = [(url, times)]
				else:
					sfs[sf].append((url, times))

	print("\n\n")
	
	print("Surface forms que conducen a varias entities distintas")
	for sf in sfs:
		urlList = sfs[sf]
		if len(urlList) > 1:
			print("\nSF=", sf, " -->", end=' ')
			for url in urlList:
				print(url[0].split("/")[-1], "(", url[1], ")", ",", end='')
	




# si hay exactamente un parámetro, ok 
if len(sys.argv) == 2:
	origin = sys.argv[1]
	
	ext = origin[-1]
	if ext != "p":
		print("El fichero "+origin+" no tiene extensión '.p'")
		exit(-1)
		
		
		
# si no hay exactamente un parámetro, mal
else:
	print("Usa: "+sys.argv[0]+" fichero|directorio")
	exit(-1)


createReport(sys.argv[1])

	


	
