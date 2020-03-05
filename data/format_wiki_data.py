import pandas as pd
import mwparserfromhell
import json_lines
import os,sys

this_filename = sys.argv[0]
this_abs_path = os.path.abspath(this_filename)
cwd = os.path.abspath(this_filename+"/..")

json_filename = cwd+"/solved.jsonl"

datalist = []

with open(json_filename, 'rb') as f: # opening file in binary(rb) mode    
    for idx,item in enumerate(json_lines.reader(f)):
        print(">> ",idx," | ",item['pageTitle'])
        POV_wikicode = mwparserfromhell.parse(item['povVersion'])
        POV_text = POV_wikicode.strip_code()
        SPOV_wikicode = mwparserfromhell.parse(item['solvedpovVersion'])
        SPOV_text = SPOV_wikicode.strip_code()
        datalist.append([POV_text,'POV'])
        datalist.append([SPOV_text,'SPOV'])

df = pd.DataFrame(datalist, columns = ['body','label'])
df.to_csv(cwd+"/data.csv", index = False)
