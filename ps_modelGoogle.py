# lanzar en segundo plano con python 2.7


from flask import Flask, request, flash, json, make_response
import gensim
import pickle
from gensim.models import KeyedVectors
from gensim.models import Phrases, Word2Vec

app = Flask(__name__)

model = KeyedVectors.load_word2vec_format("./models/GoogleNews-vectors-negative300.bin.gz", binary=True)

@app.route("/model/<path:modelAttrs>",  methods=["GET"])
def getAttrs(modelAttrs):
	splited = modelAttrs.split('/')
	aux = model
	for p in splited:
		aux = getattr(aux, p)

	if callable(aux) and len(request.args) > 0:
		unNamed = []
		named = {}
		for k, v in request.args.items():
			if k.startswith("arg"):
				unNamed.append(v)
			else:
				try:
					value = int(v)

					if len(v) == len(str(value)):
						named[k] = value
					else:
						named[k] = v

				except ValueError:
					named[k] = v

		app.logger.info(unNamed)
		app.logger.info(named)
		aux = aux(*unNamed, **named)
	elif callable(aux) and len(request.args) == 0:
		return ""

	response = make_response(pickle.dumps(aux, protocol=pickle.HIGHEST_PROTOCOL))
	response.headers.set('Content-Type', 'application/octet-stream')
	response.headers.set('Content-Disposition', 'attachment', filename='data')
	return response

if __name__ == '__main__':
	app.run(host='0.0.0.0', port=9100)
