import time

from box_ACT import class_select
from box_aram import touch_aramlist_images
from box_book import touch_booklist_images
from box_mew import touch_mewlist_images
from box_tv import touch_tvlist_images
from download_thumbnails import *
from request_API import *


# WittiBox content verification
def check_wittibox(childIds, childNms, authToken, server, inputId):
    child_pairs = list(zip(childIds, childNms))
    if not child_pairs:
        print("[WARN] No child info found. Skip WittiBox verification.")
        return False

    loop_items = []
    try:
        class_resp = class_list(authToken, inputId, server)
        if class_resp is not None:
            class_items = class_resp.json().get("result", {}).get("classList", [])
            for cls in class_items:
                class_id = str(cls.get("classId", "")).strip()
                class_nm = str(cls.get("classNm", "")).strip()
                if not class_id or not class_nm:
                    continue

                student_resp = student_list_by_class(authToken, class_id, server)
                if student_resp is None:
                    print(f"[WARN] student_list_by_class failed for classId={class_id}. skip class={class_nm}")
                    continue

                students = student_resp.json().get("result", {}).get("studentList", [])
                if not students:
                    print(f"[WARN] no students for classId={class_id}. skip class={class_nm}")
                    continue

                first_student = students[0]
                student_id = str(first_student.get("studentId", "")).strip()
                student_nm = str(first_student.get("studentNm", "")).strip() or class_nm
                login_id = str(
                    first_student.get("loginId")
                    or first_student.get("studentLoginId")
                    or inputId
                ).strip()
                if not student_id:
                    print(f"[WARN] first student has no studentId for classId={class_id}. skip class={class_nm}")
                    continue

                study_access = authenticate_study_access_detailed(student_id, login_id, server)
                if not study_access or not study_access.get("ok"):
                    print(
                        f"[WARN] study/access failed for class={class_nm}, "
                        f"studentId={student_id}, loginId={login_id}"
                    )
                    continue

                result = (study_access.get("data") or {}).get("result", {})
                child_id = str(result.get("memId", "")).strip()
                child_auth_token = str(result.get("authToken", "")).strip()
                child_mem_nm = str(result.get("memNm", "")).strip() or student_nm
                if not child_id or not child_auth_token:
                    print(
                        f"[WARN] study/access missing memId/authToken for class={class_nm}, "
                        f"studentId={student_id}"
                    )
                    continue

                loop_items.append({
                    "classNm": class_nm,
                    "childId": child_id,
                    "childNm": child_mem_nm,
                    "authToken": child_auth_token,
                })

            class_count = len(loop_items)
            print(
                f"[INFO] WittiBox loop count = {class_count} "
                f"(classList={class_count})"
            )
        else:
            print("[WARN] class_list response is None. Fallback to child count.")
    except Exception as e:
        print(f"[WARN] Failed to read class_list count. Fallback to child count: {e!r}")

    if not loop_items:
        loop_items = [
            {
                "classNm": child_pairs[0][1],
                "childId": child_pairs[0][0],
                "childNm": child_pairs[0][1],
                "authToken": authToken,
            }
        ]
        print("[WARN] class-based child mapping unavailable. Fallback to study/access child info.")

    for idx, item in enumerate(loop_items):
        childId = item["childId"]
        childNm = item["childNm"]
        childAuthToken = item.get("authToken") or authToken
        try:
            target_class_nm = item["classNm"]
            file_prefix = target_class_nm or childNm
            class_changed = class_select(target_class_nm)
            if not class_changed:
                print(f"[ERROR] class_select failed for target='{target_class_nm}'. stop WittiBox test.")
                return False

            curriculum_resp = get_curriculum_response(childAuthToken, childId, server)
            if curriculum_resp is None:
                print(
                    f"[ERROR] curriculum load failed for class={target_class_nm}, "
                    f"childId={childId}, childNm={childNm}"
                )
                return False
            curriculum_data = curriculum_resp.json()
            print(
                f"=== class[{idx}]={target_class_nm}, childId={childId}, "
                f"childNm={childNm} curriculum loaded ==="
            )

            content_info = download_all_thumbnails(file_prefix, curriculum_data, server)
            time.sleep(2)

            if not touch_booklist_images(file_prefix):
                return False
            time.sleep(2)
            if not touch_aramlist_images(file_prefix, content_info=content_info):
                return False
            time.sleep(2)
            if not touch_mewlist_images(file_prefix):
                return False
            time.sleep(2)
            if not touch_tvlist_images(file_prefix):
                return False
            time.sleep(2)

        except Exception as e:
            print(f"[WARN] Failed to process {childNm}: {e!r}")
            return False

    return True
