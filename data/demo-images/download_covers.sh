#!/bin/bash
#
# Download random book cover images from Open Library
# Starts at image 05 (01-04 are user-provided images)
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

START_NUM=5
END_NUM=45
TOTAL_IMAGES=$((END_NUM - START_NUM + 1))

echo "📚 Downloading $TOTAL_IMAGES book covers from Open Library..."
echo "Starting at image $(printf "%04d" $START_NUM)"
echo ""

# Counter for successful downloads
SUCCESS_COUNT=0
FAIL_COUNT=0

# Open Library has book IDs (OL...M format)
# We'll use a range of known book IDs
# Open Library book IDs are sequential, so we can iterate through them

for i in $(seq $START_NUM $END_NUM); do
    PADDED_NUM=$(printf "%04d" $i)
    OUTPUT_FILE="book_${PADDED_NUM}.jpg"

    # Skip if file already exists
    if [ -f "$OUTPUT_FILE" ]; then
        echo "⏭️  Skipping $OUTPUT_FILE (already exists)"
        ((SUCCESS_COUNT++))
        continue
    fi

    # Generate Open Library book ID (offset by a base number to get variety)
    # OL book IDs are like OL45804M, OL45805M, etc.
    BASE_OFFSET=45800
    BOOK_ID=$((i + BASE_OFFSET))
    OL_ID="OL${BOOK_ID}M"

    # Try Open Library cover API
    COVER_URL="https://covers.openlibrary.org/b/olid/${OL_ID}-L.jpg"

    # Download with curl, follow redirects, fail silently on 404
    HTTP_CODE=$(curl -L -s -w "%{http_code}" -o "$OUTPUT_FILE" "$COVER_URL")

    if [ "$HTTP_CODE" == "200" ]; then
        # Check if it's actually an image (not the default "no cover" response)
        FILE_SIZE=$(stat -f%z "$OUTPUT_FILE" 2>/dev/null || stat -c%s "$OUTPUT_FILE" 2>/dev/null)

        if [ "$FILE_SIZE" -gt 1000 ]; then
            echo "✅ Downloaded $OUTPUT_FILE (${OL_ID}, ${FILE_SIZE} bytes)"
            ((SUCCESS_COUNT++))
        else
            # Small file, probably no cover available
            rm -f "$OUTPUT_FILE"

            # Try alternate method: use ISBN range
            # Generate pseudo-random ISBN-10
            ISBN="97801$((RANDOM % 90000 + 10000))$(printf "%04d" $((i % 10000)))"
            COVER_URL="https://covers.openlibrary.org/b/isbn/${ISBN}-L.jpg"

            HTTP_CODE=$(curl -L -s -w "%{http_code}" -o "$OUTPUT_FILE" "$COVER_URL")

            if [ "$HTTP_CODE" == "200" ]; then
                FILE_SIZE=$(stat -f%z "$OUTPUT_FILE" 2>/dev/null || stat -c%s "$OUTPUT_FILE" 2>/dev/null)
                if [ "$FILE_SIZE" -gt 1000 ]; then
                    echo "✅ Downloaded $OUTPUT_FILE (ISBN ${ISBN}, ${FILE_SIZE} bytes)"
                    ((SUCCESS_COUNT++))
                else
                    rm -f "$OUTPUT_FILE"
                    echo "⚠️  Skipped $OUTPUT_FILE (no cover available)"
                    ((FAIL_COUNT++))
                fi
            else
                rm -f "$OUTPUT_FILE"
                echo "⚠️  Skipped $OUTPUT_FILE (no cover available)"
                ((FAIL_COUNT++))
            fi
        fi
    else
        rm -f "$OUTPUT_FILE"
        echo "⚠️  Skipped $OUTPUT_FILE (HTTP $HTTP_CODE)"
        ((FAIL_COUNT++))
    fi

    # Progress update every 50 images
    if [ $((i % 50)) -eq 0 ]; then
        echo ""
        echo "📊 Progress: $((i - START_NUM + 1))/$TOTAL_IMAGES images processed"
        echo "   ✅ Success: $SUCCESS_COUNT | ⚠️  Failed: $FAIL_COUNT"
        echo ""
    fi

    # Rate limit: be nice to Open Library servers
    sleep 0.5
done

echo ""
echo "="
echo "✨ Download complete!"
echo "   Total processed: $TOTAL_IMAGES"
echo "   Successfully downloaded: $SUCCESS_COUNT"
echo "   Failed: $FAIL_COUNT"
echo ""
echo "Next steps:"
echo "  1. Create ZIP: zip -r books.zip *.jpg"
echo "  2. Upload: aws s3 cp books.zip s3://\$(aws s3 ls | grep landing | awk '{print \$3}')/books.zip"
