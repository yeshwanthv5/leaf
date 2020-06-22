#!/usr/bin/env bash

# download data and convert to .json format

MAX_WRITERS=100
DATA_PARTITION=0

#if [ ! -d "data/all_data" ] || [ ! "$(ls -A data/all_data)" ]; then
#    cd preprocess
#    ./data_to_json.sh $MAX_WRITERS $DATA_PARTITION
#    cd ..
#fi

NAME="femnist" # name of the dataset, equivalent to directory name

cd ../utils

./preprocess.sh --name $NAME --mw $MAX_WRITERS --dp $DATA_PARTITION $@

cd ../$NAME
