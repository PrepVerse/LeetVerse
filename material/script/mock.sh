#!/bin/bash

py material/script/readme_writer_main.py
py material/script/mkdocs_writer_main.py --mock

cp README.md docs/preface.md

mkdocs serve -f mkdocs.yml
