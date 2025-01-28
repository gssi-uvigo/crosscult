# These are the functions to process a text content
# it is also used by the main program, so it has been put in its own file

import re

# regexp that matches a word beginning uppercase followed by a space and roman number, ended by a not alphanumeric character   (we call it EVENT)
reg_WordWithRomanNumber = re.compile('([A-Z]\w+) (?=[MDCLXVI])(M*)(C[MD]|D?C{0,3})(X[CL]|L?X{0,3})(I[XV]|V?I{0,3})(\W)')


# aux functions 

# to change a newline by a space in a string 
def rnl (cad):
	return cad.replace("\n", " ")


# to build the string describing a non-changed match, without using non-existing indices of the words vector
def buildSecureReject (words, j):
	if j-4 < 0:
		w_4 = ""
	else:
		w_4 = words[j-4]
	if j-3 < 0:
		w_3 = ""
	else:
		w_3 = words[j-3]
	if j-2 < 0:
		w_2 = ""
	else:
		w_2 = words[j-2]	
	if j-1 < 0:
		w_1 = ""
	else:
		w_1 = words[j-1]
	if j+1 > len(words)-1:
		w1 = ""
	else:
		w1 = words[j+1]
	if j+2 > len(words)-1:
		w2 = ""
	else:
		w2 = words[j+2]
	if j+3 > len(words)-1:
		w3 = ""
	else:
		w3 = words[j+3]
	if j+4 > len(words)-1:
		w4 = ""
	else:
		w4 = words[j+4]
	txt = rnl(w_4+w_3+w_2+w_1+words[j]+w1+w2+w3+w4)
	html = 	txt = rnl(w_4+w_3+w_2+w_1+"<span style='color: red'>"+words[j]+"</span>"+w1+w2+w3+w4)
	
	return(txt,html)


# to decide if a word starting by uppercase is proper name or not
# it is not a complete function, it is a repository of heuristics, there are much more cases (we need a better solution)
def isProperName (n):
	words = {"King", "Queen", "BC", "AD", "From"} 
	if n in words:
		return False
	return True

# to decide if a group of characters contains a char marking the end of a sentence, that is, avoiding the previous and the next words to form a proper name
def hasSentenceEnd (g):
	if g.find(".") != -1 or g.find(";") != -1 or g.find(":") != -1 or g.find(",") != -1 or g.find("!") != -1 or g.find("?") != -1 or g.find("(") != -1 or g.find(")") != -1 \
		or g.find("[") != -1 or g.find("]") != -1 or g.find("{") != -1 or g.find("}") != -1 or g.find("'") != -1 or g.find(chr(8217)) != -1 or g.find(chr(8216)) != -1:
		return True
	return False

# to decide if to add or not a suffix to a NAME depending on its surroundings 
# if it is followed by an uppercase word (without a mark of sentence end in middle) it is not changed
# if it is preceded by an uppercase (proper name) word (without a mark of sentence end in middle) it is not changed 
def changeAccordingContext  (words, j):
	if j+2 < len(words):
		if words[j+2].isidentifier() and words[j+2][0].isupper() and not hasSentenceEnd(words[j+1]):
			return False
	if j-1 >= 0:
		if hasSentenceEnd(words[j-1]):
			return True;
	if j-3 >= 0:
		if words[j-2].isidentifier() and words[j-2][0].isupper() and isProperName(words[j-2])  and  not hasSentenceEnd(words[j-3]):
			return False
	elif j-2 > 0:
		if words[j-2].isidentifier() and words[j-2][0].isupper() and isProperName(words[j-2]):
			return False
	
	return True

	

# to process a content and return the result   
def processContent (content):
	
	# this is an offset dict, keys are offsets, values the detected matches (object with name and EVENT) in that offset
	wordsWithNumber = {}
	
	# this is a dict of names, keys are name of matches, values are sets with all the different EVENTS involving such name  
	allSubstitutions = {}
		
	# first pass to content, to detect and store EVENTS
			
	# match is every case finding EVENTS 
	for match in reg_WordWithRomanNumber.finditer(content):
		offset = match.start() # the position of the EVENT 
		# match.groups provides the different parts of the match
		tuplaGroups1 = match.groups()[:-1] # remove the non-alphanumeric char ending the sequence   
		tuplaGroups2 = (tuplaGroups1[0]," ")+tuplaGroups1[1:] # add a ' ' after the name
		newFullWord = "".join(tuplaGroups2) # join all parts, without spaces, result is "name romannumber"
		print(match.groups(), " --> ", tuplaGroups2, " --> ", newFullWord)

		word = match.group(1) # the name
		# add the match to the dict of offsets, key the offset, value an object with the name (word) and the match (fullWord)
		wordsWithNumber[offset] = {"fullWord": newFullWord.strip(), "word": word}   # strip removes spaces before and after the string
		
		# add the EVENT to the dict of names, a set with all the EVENT of such name
		if word not in  allSubstitutions:
			allSubstitutions[word] = {newFullWord}
		else:
			allSubstitutions[word].add(newFullWord)

	print('\n-------- Results of the first pass --------')
	
	print("There are", len(wordsWithNumber), "EVENTS, proper names followed by an space and a roman number")
	
	# EVENTS have been detected. Let's go with changes
	
	# second pass to the content, to make modifications (changes after EVENT or before for unique NAMEs)
	# we study the content from offset to offset, and make modifications depending on current substitutions 

	offsets = list(wordsWithNumber.keys())  # list of offsets of every EVENT
	offsets.sort()  # ascending order
	
	negReportTxt = ""    # text negative report (transformations not done)
	negReportHtml = ""   # html negative report
	
	if len(offsets) == 0:
		return None

	
	# dict to storecurrent substitutions, key is the name, value is object with the EVENT and its offset (not necessary)
	currentSubstitutions = {}
	

	# start with the initial text, before the first EVENT
	initial= content[0:offsets[0]]
	
	# convert the string to a list of words separated by non-alphanumeric chars
	# with the parenthesis, the detected groups marking the word separation are also returned, that is, 
	# words is a list contaning everything in the string, the words and, between them, the non-alphanumeric groups separating them
	words = re.split('(\W+)', initial)
	wordsHTML = re.split('(\W+)', initial)  # the same for the HTML result
	
	for j in range(0, len(words)):
		if words[j] in allSubstitutions:
			if len(allSubstitutions[words[j]]) == 1:
				sustituto = list(allSubstitutions[words[j]])[0]  # to get the only one set member
				if changeAccordingContext(words, j): 
					# change is done					
					words[j] = sustituto
					wordsHTML[j] = "<span style='color: green'><b>"+sustituto+"</b></span>"
				else:
					# change is not done, and it is annotated in the negative report
					negReportTxt += "Before: ("+sustituto+")  -->  **" 
					negReportTxt += buildSecureReject(words, j)[0]+"**\n"
					negReportHtml += "Before: ("+sustituto+")  -->  **" 
					negReportHtml += buildSecureReject(words, j)[1]+"**<p>"

	# 'finalContent' contains the text after processing and  changes
	finalContent = "".join(words)
	finalContentHTML = "".join(wordsHTML).replace("\n", "<p>") 
	
	# let's go with rest of text after the first offset
	
	for i in range(0, len(offsets)):  # range(0,n) goes from 0 to n-1
		o = wordsWithNumber[offsets[i]] # the object with the i event, we study the text from here to the following

		# add the event to the final content and to the dict of current substituions
		finalContent += o["fullWord"]
		finalContentHTML += o["fullWord"]
		
		currentSubstitutions[o["word"]] = {"sub": o["fullWord"], "offset": offsets[i]}  # if that word already existed, it is changed by the new one

		# search the limit of the text fragment, from teh current event to the following one (or teh end of text)
		if i+1 == len(offsets):
			limit = len(content)  # this was the last event, limit is the length of the original text
		else:
			limit = offsets[i+1]  # limit is the offset of the following event

		# take the string from the current offset + len(added) to the limit
		currentSubstring = content[offsets[i]+len(o["fullWord"]):limit]
		
		# convert such string to a list of words separated by non-alphanumeric chars 
		# with the parenthesis, the detected groups marking the word separation are also returned, that is, 
		# words is a list contaning everything in the string, the words and, between them, the non-alphanumeric groups separating them
		words = re.split('(\W+)', currentSubstring)
		wordsHTML = re.split('(\W+)', currentSubstring)
		
		# study each one of the words in list, that is, of the string after the current event to limit
		for j in range(0, len(words)):
			# if current word is in the list of substitutions, change it
			if words[j] in currentSubstitutions:
				sustituto = currentSubstitutions[words[j]]["sub"]
				if changeAccordingContext(words, j):
					# change is done 
					words[j] = sustituto
					wordsHTML[j] = "<span style='color: green'><b>"+sustituto+"</b></span>"
				else:
					# change is not done, and it is annotated in the negative report
					negReportTxt += "After: ("+sustituto+")  -->  **"
					negReportTxt +=  buildSecureReject(words, j)[0]+"**\n"
					negReportHtml += "After: ("+sustituto+")  -->  **"
					negReportHtml += buildSecureReject(words, j)[1]+"**<p>"
			else:
				if words[j] in allSubstitutions:
					if len(allSubstitutions[words[j]]) == 1:
						sustituto = list(allSubstitutions[words[j]])[0]
						if changeAccordingContext(words, j):
							# change is done 
							words[j] = sustituto
							wordsHTML[j] = "<span style='color: green'><b>"+sustituto+"</b></span>"
						else:
							# change is not done, and it is annotated in the negative report
							negReportTxt += "Before: ("+sustituto+")  -->  **"
							negReportTxt +=  buildSecureReject(words, j)[0]+"**\n"
							negReportHtml += "Before: ("+sustituto+")  -->  **"
							negReportHtml += buildSecureReject(words, j)[1]+"**<p>"

		# rebuild the studied fragment from the list of words, and add it to the final content
		finalContent += "".join(words)  
		finalContentHTML += "".join(wordsHTML).replace("\n", "<p>")
	
	return (finalContent, finalContentHTML, negReportTxt, negReportHtml)


