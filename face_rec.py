import threading
import face_recognition
import cv2
import time
import nfc
from pymongo import MongoClient


recently_scanned_tags = {}
Tag_dedup = 2
cluster = MongoClient("mongodb+srv://bernardorhyshunch:TakingInventoryIsFun@cluster0.jpb6w.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0")
db = cluster["Inventory"]
collection1 = db["astro"]
collection = db["Inventory"]


class NFCReaderThread(threading.Thread):
    def __init__(self, stop_event):
        super().__init__()
        self.result = None
        self.error = None
        self.stop_event = stop_event
    def run(self):
        try:
            self.result = nfc_read(self.stop_event)
        except Exception as e:
            self.error = e

def load_known_faces():
    known_faces = []
    try:
        # Load all reference faces
        for i in range(0, 8):
            img = face_recognition.load_image_file(f"pictures/face{i}.jpg")
            encoding = face_recognition.face_encodings(img)[0]
            known_faces.append(encoding)
        return known_faces
    except FileNotFoundError:
        print("one or more face images not found in 'pictures' directory")
        pass
    except IndexError:
        print("Error: No face detected in one or more reference images")
        exit(1)

def capture_and_compare(cap, known_faces):
    """Capture a frame and compare with known faces"""
    ret, frame = cap.read()
    if not ret:
        print("Error: Cannot read from webcam")
        return None

    try:
        # Get encoding of face in current frame
        current_face_encoding = face_recognition.face_encodings(frame)[0]
        print("current face encoding")
        # Compare with known faces
        results = face_recognition.compare_faces(known_faces, current_face_encoding)
        # Get indices of matching faces
        matches = [index for index, value in enumerate(results) if bool(value)]
        return matches

    except IndexError:
        print("No face detected in camera frame")
        return None

def idnumber(tag_data):
    if "NFCNASAMED" in str(tag_data):
        print("scanned" + str(tag_data))
        splitmeds = str(tag_data).split('%')
        intmeds = int(splitmeds[2])
        return intmeds

    else:
        print("med unknown tag")

def nfc_read(stop_event):
    time.sleep(1)
    with nfc.ContactlessFrontend('usb:072f:2200') as clf:
        while not stop_event.is_set():
            tag = clf.connect(rdwr=
            {
                'targets': ['106A'],
                'on-connect' : lambda tag: False
            },
            terminate=lambda: stop_event.is_set(), timeout=0.1

            )

            if tag is not None:
                if not tag.ndef:
                    print("no ndef data")
                    return None
                tag_data = tag.ndef.records

            if tag is None:
                continue

            if tag_data is None:
                print("no tag data")
                return

            id_num = idnumber(tag_data)
            if id_num is not None:
                current_time = time.time()

                # Check if the tag was recently scanned
                if id_num in recently_scanned_tags:
                    last_scanned_time = recently_scanned_tags[id_num]
                    if current_time - last_scanned_time < Tag_dedup:
                        print(f"Tag {id_num} was already scanned recently. Ignoring duplicate...")
                        return None

                # Update the cache with the current scan time
                recently_scanned_tags[id_num] = current_time
                return id_num

        if id_num is None:
            print("no id num data")
            return



def check_value_with_timeout(timeout_seconds):
    print("Waiting for NFC tag with timeout...")

    # Start NFCReaderThread, which runs nfc_read() in the background
    stop_event = threading.Event()
    nfc_thread = NFCReaderThread(stop_event)
    nfc_thread.start()  # Start running the thread

    nfc_thread.join(timeout_seconds)

    if nfc_thread.is_alive():
        print("NFC read timeout reached, stopping NFC read...")
        stop_event.set()
        nfc_thread.join()
        return None

    if nfc_thread.error:
        print(f"Error in NFC reader: {nfc_thread.error}")
        return None

    print(f"NFC Read Result: {nfc_thread.result}")
    return nfc_thread.result

def db_edit_face(matches, intmeds):
    idastro = int(matches[0])
    if intmeds is not None and idastro is not None:
        field_name = f"Amount_{intmeds}"
        collection1.update_many({"_id": idastro}, {"$inc": {field_name: +1}})
        print(f"face matches with {idastro} :D ")
        return

    if idastro is None:
        print("no matching face data")
        return
    if intmeds is None:
        print("eeeeee")
def main():
    # Initialize webcam
    cap = cv2.VideoCapture(0)
    print("webcam started")
    try:
        known_faces = load_known_faces()
        print("known faces loaded")
    except Exception as e:
        print(f"Error: {e}")
        return

    while True:
        if not cap.isOpened():
            print("Error: Cannot open webcam")
            return

        try:
            # Load known faces
            # Capture and process one frame
            matches = capture_and_compare(cap, known_faces)
            result = check_value_with_timeout(5)
            print(matches)

            if matches:
                try:
                    if result is None:
                        print("no nfc tag scanned")
                        continue

                    if result is not None:
                        intmeds = result
                        if intmeds:
                            collection.update_many(
                                {"_id": intmeds},
                               {"$inc": {"Amount": -1}
                                })
                            db_edit_face(matches, intmeds)
                            print(intmeds)
                            time.sleep(2)
                            print("ready")
                        else:
                            print("no nfc tag scanned")
                    else:
                        print("AAAAAAAAAAAAAA")
                        continue
                except AttributeError:
                    print("no tag data")
            else:
                print("No matching face detected")
                time.sleep(2)
                print("ready")

        except KeyboardInterrupt:
            # Clean up
            cap.release()
            cv2.destroyAllWindows()

if __name__ == "__main__":
    main()