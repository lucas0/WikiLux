
#this is the data extracted from the jsonl you've sent me
data_wiki.csv

#some initial cleaning is done on this data and that is the input data for the model. It is loaded on data_loader.py and a shuffled subset of that is used by the model and saved as data.csv
data_wiki_clean.csv

#csv of the data that was last processed by the model, in case there is no modification on that, the model can skip the feature generation steps, which saves a LOT of time
data.csv
