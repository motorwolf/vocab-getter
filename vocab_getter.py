import sqlite3
import pdb
import requests
import json, pprint, shelve, csv
import os

pp = pprint.PrettyPrinter(indent=4)

db = sqlite3.connect('./vocab.db', uri=True)
c = db.cursor()
query =  '''SELECT w.stem, l.usage FROM words as w INNER JOIN lookups as l on w.id = l.word_key'''
results = list(c.execute(query))

base_url = 'https://od-api.oxforddictionaries.com:443/api/v2/'
APP_ID = os.environ.get("APP_ID")
API_KEY = os.environ.get("API_KEY")
language = 'en-us'
query_url = base_url + 'entries/' + language + '/'

def make_request(word):
    url = query_url + word
    r = requests.get(url, headers={"app_id": APP_ID, "app_key": API_KEY}).json()
    return r

def fetch_word(word):
    try:
        url = query_url + word
        print(url)
        r = requests.get(url, headers={"app_id": APP_ID, "app_key": API_KEY}).json()
        if 'error' in r:
            return {
                'error': f"No definition found for: {word}."
            }
        res_word = r['id']
        word_info = r['results'][0]['lexicalEntries'][0]['entries'][0]['senses'][0]
        word_info['word'] = res_word
        return word_info
    except:
        print('Something went wrong with API call.')
        breakpoint()

def format_result(result):
    try:
        if 'error' in result:
            return {
                'word': 'error',
                'definition': result['error'],
                'synonyms': [],
                'examples': [],
            }
        if 'word' in result:
            word = result['word']
        else: 
            word = None
        if 'definitions' not in result and 'crossReferences' in result:
            return format_result(fetch_word(result['crossReferences'][0]['id']))
        if 'definitions' not in result:
            return {
                'word': result['word'],
                'definition': 'There was a problem defining this word.',
                'synonyms': [],
                'examples': [],
            }
        definition = result['definitions']
        examples = result.get('examples', [])
        #shortDef = result['shortDefinitions']
        if 'synonyms' in result:
            synonyms_raw = list(filter(lambda x: x['language'] == 'en', result['synonyms']))
            synonyms = list(map(lambda x: x['text'], synonyms_raw))
        else:
            synonyms = []
        subsenses = []
        if 'subsenses' in result:
            subsenses = list(map(format_result, result['subsenses']))

        relevant_info = {
            'word': word,
            'definition': definition,
            'examples': examples,
            #'shortDef': shortDef,
            'synonyms': synonyms,
        }
        if subsenses:
            subsenses.insert(0,relevant_info)
            return subsenses

        return relevant_info
    except:
        return {
            'word': 'error',
            'definition': 'error',
            'examples': 'error',
            'synonyms': 'error',
        }


def formatted_example(word, example):
    text = example if type(example) is str else example['text']
    text_bold = text.replace(word, f'<b>{word}</b>')
    word_length = len(text.split(' '))
    if word_length > 44:
        try:
            pin_word = f'<b>{word}</b>'
            cut_sentence = text.split(word)
            first_half = ' '.join(cut_sentence[0].split(' ')[-10:])
            last_half = ' '.join(cut_sentence[1].split(' ')[:10])
            return '<i> ...' + first_half + pin_word + last_half + '... </i>'
        except:
            print("The word was not found in this example.")

    return '<i>' + text_bold + '</i>'

def format_list_result(result):
    try:
        word = result[0]['word']
        definition = ''
        examples = 'EXAMPLES: <br>'
        synonyms = 'SYNONYMS: <br>'
        for index, wdef in enumerate (result, 1):
            if wdef['definition'] == 'error':
                continue
            if wdef['examples']: 
                ex = f'{index}. ' + '\n'.join(list(map(lambda t: formatted_example(word, t), wdef['examples']))) + '\n'
            else:
                ex = ''
            syn = f'{index}. ' + ', '.join(wdef['synonyms']) + '\n' if wdef['synonyms'] else ''

            de = wdef['definition'] if word == 'error' else f'{index}. ' + wdef['definition'][0] + ' \n '
            definition += de
            examples += ex 
            synonyms += syn

        relevant_info = {
            'word': '<b>' + word + '</b>',
            'definition': definition,
            'examples': examples,
            'synonyms': synonyms,
        }

        return relevant_info
    except:
        return {
            'word': 'error',
            'definition': 'error',
            'examples': 'error',
            'synonyms': 'error',
        }

def lookup_words(words):
    """ Words is a list of tuples representing new vocabulary words to get.
    The tuple first entry is the raw word, the second entry is the stem,
    which is the word cleaned of its tense endings and pluralizations, 
    and the third item is the passage from which the word was looked up."""
    defined_words = []
    for vocab_word in words:
        try:
            word, usage = vocab_word
            my_example = formatted_example(word, usage)
            result = format_result(fetch_word(word))
            # result can either be a list or a dict.
            result = result if type(result) == list else [result]
            result = format_list_result(result)
            col1 = result['word']
            col2 = '<hr>'.join([result['definition'], result['synonyms'], result['examples'], my_example])
            pp.pprint(result.values())
            defined_words.append([col1, col2])
        except:
            defined_words.append(['Error: Something went wrong.'])
    return defined_words

def make_db_csv(db_results):
    with open('db_words.csv', 'w', newline='') as csvfile:
        db_wordwriter = csv.writer(csvfile, delimiter=';', quotechar='"', quoting=csv.QUOTE_MINIMAL)
        db_wordwriter.writerow(['WORD', 'MYEXAMPLE'])
        for row in db_results:
            db_wordwriter.writerow(row)

def consume_db_csv():
    with open('db_words_edited.csv', newline='') as csvfile:
        wordreader = csv.reader(csvfile, delimiter=';', quotechar='"')
        return list(wordreader)


def make_csv(rows):
    with open('vocab.csv', 'a', newline='') as csvfile:
        wordwriter = csv.writer(csvfile, delimiter=';',
                                quotechar='"', quoting=csv.QUOTE_MINIMAL)
        wordwriter.writerow(['WORD', 'DEFINITION'])
        for row in rows:
            wordwriter.writerow(row)

# TEST RUN
###################
#test_db_results = [('moribund', 'This word has ] many definitions.'), ('vituperation', 'This word has one definition.'), ('sabayon', 'This is a cross-referenced word.'), ('frenzying', 'This is not a word.(But maybe it should be?)'), ('flum·mer·y', 'Weird formatting'), ('in camera', "Phrases"), ("ELENCHUS", "ALL FRIGGIN CAPS!!!")]
#test_api_results = lookup_words(test_db_results)
#make_csv(test_api_results)
###################
# ERROR DATA
# wrong = 'wrong_thing'
# wrong_results = lookup_words(wrong)
# more_wrong = format_list_result('wrong')
# more_wrong2 = format_result('wrong') 
###################
# PREP DATA - run this command to get your words
#make_db_csv(results)
###################
# CONSUME PREPPED DATA - run these commands after data is prepped
#consumed_csv = consume_db_csv()
#api_results = lookup_words(consumed_csv)
#make_csv(api_results)
###################
# TEST INDIVIDUAL WORDS
#word1 = fetch_word('rebarbative')
#word2 = fetch_word('vituperation')
#word1f = format_result(word1)
#word2f = format_result(word2)

#pp.pprint(word1)
#pp.pprint(word2)