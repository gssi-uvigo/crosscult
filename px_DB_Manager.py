from requests_futures.sessions import FuturesSession
from px_aux import URL_DB as _URL_DB


# to get wikicats and subjects from a text
# receives: the text
# returns: a dictionary result:
#    result['error']  with a message (string), or
#    result['wikicats'] with a list of wikicats (strings)
#    result['subjects'] with a list of subjects (strings)
def getCategoriesInText(texto):
	import requests
	from px_aux import URL_DB_SL_annotate as _URL_DB_SL_annotate
	
	result = {}
	
	try:
		annotateTextRequest = requests.get(_URL_DB_SL_annotate, params={"text": texto, "confidence": 0.5, "support": 1}, headers={"Accept": "application/json"})
	except Exception as e:
		print("Problem querying DB-SL")
		result["error"] = "Problem with DB-SL --> "+str(e)
		return result;
	
	dbpediaManager = DBManager()
	try:
		dbpediaText = annotateTextRequest.json()
	except Exception as e:
		print(annotateTextRequest.content)
		result["error"] = "Problem with DB-SL: the query does not return the expected JSON --> "+str(e)
		return result;
	
	try:
		dbpediaManager.scanEntities(dbpediaText)
	except Exception as e:
		result["error"] = "Problem with DB-SL: error in scanEntities --> "+str(e)
		return result;
	
	entities = dbpediaManager.getEntitiesAfterOffset(0)

	if entities == []:
		result["error"] = "DBpedia does not answer to the query of types"
		return result;
	else:
		wikicats = []
		for entity in entities:
			wikicats.extend(entity["wikicats"])
			
		subjects = []
		for entity in entities:
			subjects.extend(entity["subjects"])
			
	wikicats = list(set(wikicats))  # removes duplicates
	result["wikicats"] = wikicats
	
	subjects = list(set(subjects))  # removes duplicates
	result["subjects"] = [s.split(':')[-1] for s in subjects]   # original format = http://dbpedia.org/resource/Category:Ionian_Revolt
	
	return result;
	






# to get types from a text
# receives: the text
# returns: a dictionary result:
#    result['error']  with a message (string), or
#    result['resources'] with the types for each entity (string, string list)
def getTypesInText(texto):
	import requests
	from px_aux import URL_DB_SL_annotate as _URL_DB_SL_annotate
	
	result = {}
	
	try:
		annotateTextRequest = requests.get(_URL_DB_SL_annotate, params={"text": texto, "confidence": 0.5, "support": 1}, headers={"Accept": "application/json"})
	except Exception as e:
		print("Problem querying DB-SL")
		result["error"] = "Problem with DB-SL --> "+str(e)
		return result;
	
	dbpediaManager = DBManager()
	try:
		dbpediaText = annotateTextRequest.json()
	except Exception as e:
		print(annotateTextRequest.content)
		result["error"] = "Problem with DB-SL: the query does not return the expected JSON --> "+str(e)
		return result;
	
	dbpediaManager.scanEntities(dbpediaText)
	entities = dbpediaManager.getEntitiesAfterOffset(0)

	if entities == []:
		result["error"] = "DBpedia does not answer to the query of types"
		return result;
	else:
		resources = []
		for entity in entities:
			tipos = entity["rawSparqlTypes"]
			ltipos = tipos.split(";")
			resources.append((entity['entityName'], ltipos))
	
	result["resources"] = resources
	
	return result;








# This is a class to store information about the entities detected in a text by the DBpedia SpotLight
# this info is enhanced by new queries to DBpedia
# such information is classified in three dictionaries, according to three differeny indices
# used in pp_routesCorpus.py

# These two special cases are treated this way:
# two different surfaceForms leading to the same URL  --> two entities in the list stored in such byUri URL key 
# one surfaceForm leading to several distinct URLs:  no special case

class DBManager:

	# to initialize data structures for this instance   
	def __init__(self):
		# entityData is the variable to store the information about the entities  (a dictionary with 3 dictionaries, the same info organized in 3 different ways)
		# 'byUri': {}     key=URI, value=entity list  (all the entities with the same URI and different surfaceForms)
		# 'byType': {}    key=type (string), value=entity list (all the entities with such type)
		# 'byOffset': {}  key=offset, value=entity

		self.entityData = {'byUri': {}, 'byType': {}, 'byOffset': {}}
		self.session = FuturesSession() # to manage asynchronous requests


	# function to request an entity list, the one for the URI received as parameter 
	# returns the entity list indexed in 'byUri' 
	def getByUriEntityList(self, uri):
		try:
			return self.entityData["byUri"][uri]
		except:
			return None


	# to request all the managed entities 
	# returns the dictionary 'byUri', with all the entities
	def getByUri(self):
		return self.entityData["byUri"]


	# to request all the entities whose offset is greater than the one received as parameter  
	# returns an entity list, with those entities verifying the requirement  
	def getEntitiesAfterOffset(self, offset = 0):
		return list(filter(lambda x: int(x["@offset"]) >= offset, self.entityData['byOffset'].values()))

	
	# to request all data, the structure with the 3 dictionaries
	def getDictionaries(self):
		return self.entityData
	
	# to store new data, the structure with the 3 dictionaries
	def setDictionaries(self, ed):
		self.entityData = ed
		return
	

	# to request all the entityNames a given surfaceForm leads to
	# also includes those entityNames a superString of surfaceForm leads to  (e.g. if surfaceForm='Persians', the sf 'The Persians' matches and 'the_persians' is included)
	def getEntityNamesOfSF(self, surfaceForm):
		surfaceForm2 = surfaceForm.lower()
		byUri = self.entityData["byUri"]
		sfs = {}
		
		for url in byUri:
			entityList = byUri[url]
			for entity in entityList:
				sf = entity["@surfaceForm"].lower()
				
				if sf not in sfs:
					sfs[sf] = [surfaceForm2]
				
				sfs[sf].append(entity["entityLowerName"])
		
		listaNameEntities = [surfaceForm2]
		
		for k in sfs:
			if surfaceForm2 in k:
				listaNameEntities.extend(sfs[k])

		return list(set(listaNameEntities))
		
			
			
	# to organize all info in the dictionaries
	# receives the information returned by the DB-SL containing the set of entities identified in a text
	def scanEntities(self, dbsl_output):
		try:
			dbsl_entities = dbsl_output["Resources"]
		except:
			print("Error scanning, no Resources") 
			return
		
		# obtains all URIs corresponding to the entities identified by the DB-SL
		totalUris = [x["@URI"] for x in dbsl_entities]
		noDups = list(set(totalUris))  # remove duplicates
		totalUris = ["<"+ x + ">" for x in noDups]
		totalUris = " ".join(totalUris) # builds string  "<uri1> <uri2> ...  <urin>"

		# query to obtain for each URI: label, dct:subject, rdf:type
		query = """
		SELECT ?uri ?label (group_concat(distinct ?subject; separator=';') as ?subjects) (group_concat(distinct ?type; separator=';') as ?types)   WHERE {
			VALUES ?uri {"""+ totalUris +"""} .
			?uri rdfs:label ?label; rdf:type ?type .
			?uri dct:subject ?subject .
			FILTER(regex(?type,'http://dbpedia.org/ontology|http://dbpedia.org/class/yago')) .
			FILTER(lang(?label) = 'en')}
			GROUP BY ?label ?uri
		"""
		# session is a FutureSessions object created in initialization
		requestTypes = self.session.post(_URL_DB, data={"query": query}, headers={"accept": "application/json"}) 


		# query to obtain for each URI only thos ones corresponding to persons (they have some tipical properties as birthDate, deathDate...
		query = """
		SELECT ?uri ?label (group_concat(distinct ?p; separator=';') as ?properties)  WHERE {
			VALUES ?uri {""" + totalUris + """} .
			VALUES ?p {dbo:birthDate dbo:birthPlace dbo:deathPlace dbo:deathDate dbp:birthDate dbp:birthPlace dbp:deathPlace dbp:deathDate dbo:parent dbo:commander foaf:gender} .
			?uri rdfs:label ?label; rdf:type ?t; ?p ?v .
			FILTER(lang(?label) = 'en') .
			FILTER(regex(?t,'http://dbpedia.org/ontology/Person|http://dbpedia.org/class/yago/Person'))}
			GROUP BY ?uri ?label
		"""
		requestPersonProps = self.session.post(_URL_DB, data={"query": query}, headers={"accept": "application/json"})

		# wait for query1 to complete 
		response1 = requestTypes.result()
		if response1.status_code != 200:
			print("Error querying types to DBpedia. Answer HTTP code: ", response1.status_code)
			return
	
		resultTypes = requestTypes.result().json()  # obtain the JSON result of the first one
		
		# wait for query2 to complete 
		response2 = requestPersonProps.result()
		if response2.status_code != 200:
			print("Error querying person props to DBpedia. Answer HTTP code: ", response2.status_code)
			return
		
		resultPersonProps = requestPersonProps.result().json()   # obtain the JSON result of the first one

		
		# add new fields for all entities to create enhanced entities
		dbsl_enhancedEntities = []
		for entity in dbsl_entities:
			entity["times"] = 1    # number of times that this entity appears associated to this surfaceForm ( will be increased when new ones are added)
			entity["combinedTypes"] = []
			entity["personProperties"] = []	
			entity["sparqlTypes"] = []
			entity["wikicats"] = []
			entity["subjects"] = []
			entity["rawSparqlTypes"] = []
			
			uri = entity["@URI"]
			nameEntity = uri.split("/")[-1]
			entity["entityName"] = nameEntity   # these two fields are needed for the preprocessing before training
			entity["entityLowerName"] = nameEntity.lower()
			
			dbsl_enhancedEntities.append(entity)
		
		
		# to avoid duplicates in the tupla URI/surfaceForm (it is a list of strings with such format)
		checkDuplicates = []
		
		# now study and clasify all recieved entities
		# 1. put all entities in byOffset, also put in byUri if no repeated 
		# 2. Add to byUri sparql types
		# 3. Add to byUri personProps
		# 4. Create byType with the byUri data
		# 5. Update byOffset with the new info included in byUri (sparqlTypes, Wikicats, personProps, combinedTypes...)

		
		# 1. put all enhanced entities in byOffset, also put in byUri if not repeated the pair URL/sf
		for entity in dbsl_enhancedEntities:
			# entity is a dictionary with all the fields returned by DB-SL (sec 6.4)
			# put entity in dictionary 'byOffset', with key=offset, and value the entity, even if different sf lead to the same URI
			# as DB_SL returns them in increasing order, the dictionary is ordered in such sense
			
			# this should not happen, but it happens once in our training texts, a DB-SL bug?
			if entity["@offset"] in self.entityData['byOffset']:
				print(entity["@offset"], "already asigned, not added\n", entity, "\n\n", self.entityData['byOffset'][entity["@offset"]] )
			else:	
				self.entityData['byOffset'][entity["@offset"]] = entity

			# the string URI/surfaceForm must be not duplicated to put this entity in 'byUri'
			# if duplicated, this entity is skipped for the rest of this loop, so it has only been included in byOffset with the original information
			if entity["@URI"]+"/"+entity["@surfaceForm"] not in checkDuplicates:
				# if not duplicated, the unique string is added to the checkDuplicates list 
				checkDuplicates.append(entity["@URI"]+"/"+entity["@surfaceForm"])
	
				# put the entity in byUri if not already included 
				if entity['@URI'] not in self.entityData['byUri']:
					self.entityData['byUri'][entity['@URI']] = []  # if the URI no exists, create the list

				self.entityData['byUri'][entity['@URI']].append(entity)  # add the new one  
			
			else:
				# increase 'times' for every occurrence of this URI/SF
				entityList = self.entityData['byUri'][entity['@URI']]
				for ent in entityList:
					if ent["@surfaceForm"] == entity["@surfaceForm"]:
						ent["times"] += 1
						break
					

		# now add the new types queried with SPARQL for all entities and add to 'byUri'
		# 2. Add SPARQL types to byUri 
		for rt in resultTypes["results"]["bindings"]:
			# rt is a dictionary with keys=[uri, label, subjects, types], their values are dictionaries with the payload in the field 'value' (sec 6.3)

			# process the new types and wikicats obtained with the SPARQL query
			_sparqlTypes = []
			_wikicats = []
			_rawSparqlTypes = rt["types"]["value"]

			# to isolate the new types and wikicats obtained with SPARQL 
			for _type in _rawSparqlTypes.split(";"):
				# if the type starts with "http://dbpedia.org/ontology/", is added to the list of new types (sparqlTypes), without the prefix
				if _type.startswith("http://dbpedia.org/ontology/"):
					_t = _type.replace("http://dbpedia.org/ontology/", "")
					_sparqlTypes.append(_t)
				# if the type starts with "http://dbpedia.org/class/yago/Wikicat", is added to the list of wikicats (wikicats), without the prefix
				elif _type.startswith("http://dbpedia.org/class/yago/Wikicat"):
					_t = _type.replace("http://dbpedia.org/class/yago/Wikicat", "")
					_wikicats.append(_t)
					
			uri = rt["uri"]["value"] # get the URI
			entityList = self.entityData["byUri"][uri]  # obtain the entity list from byUri corresponding to such URI
						
			# add such info to all the entities corresponding to such list
			newEntityList = []
			for entity in entityList:
				entity["sparqlTypes"] = _sparqlTypes
				entity["wikicats"] = _wikicats
				entity["subjects"] = rt["subjects"]["value"].split(";")  # copy the list of subjects, as a list
				entity["rawSparqlTypes"] = _rawSparqlTypes  # copy the raw data of the SPARQL query, a a string
				
				# create new 'combinedTypes' field	
				dbslTypes = entity["@types"].split(",")  # get the original types returned by DB-SL
				dbslTypes = list(filter(lambda x: x.startswith("DBpedia:"), dbslTypes))  # remove those not starting by 'DBpedia:'
				cleanDbslTypes = list(map(lambda x: x.replace("DBpedia:", ""), dbslTypes))  # remove the 'DBpedia:' prefix
	
				# add new field 'combinedTypes' with original+new types
				combinedTypes = list(set(cleanDbslTypes) | set(entity["sparqlTypes"]))
				entity["combinedTypes"] = combinedTypes
				
				newEntityList.append(entity)

			# put the new list in byUri, replacing the old
			self.entityData["byUri"][uri] = newEntityList


		# now the same processing with the URIs representing persons (have typical peroson props)
		# 3. Add person props to byUri 
		for rt in resultPersonProps["results"]["bindings"]:
			# rt is a dictionary with keys=[uri, label, properties], their values are dictionaries with the payload in the field 'value' (sec 6.3)
			uri = rt["uri"]["value"]  # get the URI

			entityList = self.entityData["byUri"][uri]   # obtain the entity list from byUri corresponding to such URI
			
			# add such info to all the entities corresponding to such list
			newEntityList = []
			for entity in entityList:
				entity["personProperties"] = rt["properties"]["value"].split(";")  # add a new field with person props, a list
				newEntityList.append(entity)
			
			# put the new list in byUri, replacing the old
			self.entityData["byUri"][uri] = newEntityList
			


		# now study entities indexed in byUri to create byType (a dictionary with all types, each one with the list of entities from such type) 
		# 4. Create byType with byUri data
		for entityList in self.entityData['byUri'].values():
			for entity in entityList:
				# entity runs through all the entities indexed in byUri   
				combinedTypes = entity["combinedTypes"]
	
				# study all types in this entity  
				for t in combinedTypes:
					if t not in self.entityData['byType']:  # if this type does mot exist in byType dictionary, the new key is created
						self.entityData['byType'][t] = []
					
					self.entityData['byType'][t].append(entity)   # add this entity to the list of entities of such type 



		# update the information in byOffset with such fields added after step 1
		# 5. update byOffset with new data included in byURI (sparqlTypes, Wikicats, personProps, combinedTypes...)
		for i in self.entityData['byOffset']:
			# obtain the entity corresponding to such offset i
			entity = self.entityData['byOffset'][i]
			
			# get the first entity corresponding to such URI (all of them have been populated with the same info)
			newEntityList = self.entityData["byUri"][entity["@URI"]]
			newEntity = newEntityList[0]

			# complete byOffset entity with  new fields added to the byUri entity
			entity["sparqlTypes"] = newEntity["sparqlTypes"]
			entity["wikicats"] = newEntity["wikicats"] 
			entity["combinedTypes"] = newEntity["combinedTypes"]
			entity["subjects"] = newEntity["subjects"]
			entity["rawSparqlTypes"] = newEntity["rawSparqlTypes"]
			entity["personProperties"] = newEntity["personProperties"]
			
			 # and put back the byOffset entity in byOffset, replacing the old one
			self.entityData['byOffset'][entity["@offset"]] = entity
			
			
	# to rebuild byUri and byType if byOffset has changed   
	def rebuild(self):
		newByType = {}
		newByUri = {}
		checkDuplicates = []
			
		for entity in self.getEntitiesAfterOffset(0):	
			# the string URI/surfaceForm must be not duplicated to put this entity in 'byUri'
			# if duplicated, this entity is skipped for the rest of this loop, so it has only been included in byOffset with the original information
			if entity["@URI"]+"/"+entity["@surfaceForm"] not in checkDuplicates:
				# if not duplicated, the unique string is added to the checkDuplicates list 
				checkDuplicates.append(entity["@URI"]+"/"+entity["@surfaceForm"])
		
				# put the entity in byUri if not already included 
				if entity['@URI'] not in newByUri:
					newByUri[entity['@URI']] = []  # if the URI no exists, create the list
					
				newByUri[entity['@URI']].append(entity)  # if already exists, add the new one corresponding to another sf 
		
		
			# entity runs through all the entities indexed in byOffset  
			combinedTypes = entity["combinedTypes"]
	
			# study all types in this entity  
			for t in combinedTypes:
				if t not in newByType:  # if this type does mot exist in byType dictionary, the new key is created
					newByType[t] = []
				
				newByType[t].append(entity)   # add this entity to the list of entities of such type 
		
		self.entityData["byType"] = newByType
		self.entityData["byUri"] = newByUri
	
# end DBManager