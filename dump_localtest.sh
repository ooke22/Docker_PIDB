#!/bin/bash
# Dump only the LocalTest database from Windows MongoDB (localhost:27017)

# Output directory (will be created if not existing)
DUMP_DIR="./mongo_dumps"

# Run mongodump
mongodump \
  --uri="mongodb://localhost:27017/LocalTest" \
  --out=$DUMP_DIR

echo "✅ Dump completed. Files saved in $DUMP_DIR/LocalTest"
