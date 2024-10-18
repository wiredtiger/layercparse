#!/bin/bash
twine check dist/* && twine upload `ls -1 dist/layercparse-* | LC_ALL=C sort -r`
