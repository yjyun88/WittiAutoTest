import time

from box_ACT import class_select
from box_aram import touch_aramlist_images
from box_book import touch_booklist_images
from box_mew import touch_mewlist_images
from box_tv import touch_tvlist_images
from download_thumbnails import *
from request_API import *


# WittiBox content verification
def check_wittibox(childIds, childNms, authToken, server):
    for idx, (childId, childNm) in enumerate(zip(childIds, childNms)):
        try:
            # Select class by child name
            class_select(childNm)

            # Fetch curriculum data
            curriculum_data = get_curriculum_response(authToken, childId, server).json()
            print(f"=== childId[{idx}] = {childId} curriculum loaded ===")

            # Download thumbnails for validation
            content_info = download_all_thumbnails(childNm, curriculum_data, server)
            time.sleep(2)

            # Execute touch validations
            touch_booklist_images(childNm)
            time.sleep(2)
            touch_aramlist_images(childNm)
            time.sleep(2)
            touch_mewlist_images(childNm)
            time.sleep(2)
            touch_tvlist_images(childNm)
            time.sleep(2)

        except Exception as e:
            print(f"[WARN] Failed to process {childNm}: {e!r}")
            continue
