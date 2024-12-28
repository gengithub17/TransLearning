from googletrans import Translator

def eng2jp(text:str):
		translator = Translator()
		translated = translator.translate(text, src='en', dest='ja')
		return translated.text

def jp2eng(text:str):
	translator = Translator()
	translated = translator.translate(text, src='ja', dest='en')
	return translated.text
