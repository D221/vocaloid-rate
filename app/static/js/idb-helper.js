/* exported openSyncDB, saveRequest, getAllRequests, clearRequests */

function openSyncDB() {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open("sync-requests-db", 1);
    request.onerror = () => reject("Error opening DB");
    request.onsuccess = (event) => resolve(event.target.result);
    request.onupgradeneeded = (event) => {
      const db = event.target.result;
      db.createObjectStore("requests", { autoIncrement: true });
    };
  });
}

async function saveRequest(requestData) {
  const db = await openSyncDB();
  const tx = db.transaction("requests", "readwrite");
  const store = tx.objectStore("requests");
  store.add(requestData);
  return tx.complete;
}

async function getAllRequests() {
  const db = await openSyncDB();
  const tx = db.transaction("requests", "readonly");
  const store = tx.objectStore("requests");
  return store.getAll();
}

async function clearRequests() {
  const db = await openSyncDB();
  const tx = db.transaction("requests", "readwrite");
  const store = tx.objectStore("requests");
  store.clear();
  return tx.complete;
}
