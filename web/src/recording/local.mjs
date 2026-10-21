export function openStore(userId) {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open("sales-recording-" + userId, 2);
    request.onupgradeneeded = () => {
      const db = request.result;
      if (!db.objectStoreNames.contains("epochs"))
        db.createObjectStore("epochs", { keyPath: "id" });
      if (!db.objectStoreNames.contains("blocks")) {
        const blocks = db.createObjectStore("blocks", { keyPath: "key" });
        blocks.createIndex("epoch", "epoch");
      }
      if (!db.objectStoreNames.contains("notes"))
        db.createObjectStore("notes", { keyPath: "id" });
    };
    request.onsuccess = () => {
      request.result.onversionchange = () => request.result.close();
      resolve(request.result);
    };
    request.onblocked = () => reject(new Error("请先关闭其他录音页面"));
    request.onerror = () => reject(request.error);
  });
}
export function writeNote(db, id, note, expected) {
  return new Promise((resolve, reject) => {
    const t = db.transaction("notes", "readwrite", { durability: "strict" });
    if (note) t.objectStore("notes").put({ id, ...note });
    else if (expected) {
      const r = t.objectStore("notes").get(id);
      r.onsuccess = () => {
        if (
          r.result &&
          r.result.notes === expected.notes &&
          r.result.transcript === expected.transcript
        )
          t.objectStore("notes").delete(id);
      };
    } else t.objectStore("notes").delete(id);
    t.oncomplete = () => resolve();
    t.onerror = () => reject(t.error);
    t.onabort = () => reject(t.error || new Error("本机记录保存失败"));
  });
}
export function read(db, store, key) {
  return new Promise((resolve, reject) => {
    const t = db.transaction(store, "readonly"),
      r = t.objectStore(store).get(key);
    r.onsuccess = () => resolve(r.result);
    r.onerror = () => reject(r.error);
  });
}
export function allEpochs(db) {
  return new Promise((resolve, reject) => {
    const r = db
      .transaction("epochs", "readonly")
      .objectStore("epochs")
      .getAll();
    r.onsuccess = () => resolve(r.result);
    r.onerror = () => reject(r.error);
  });
}
export function commit(db, epoch, block) {
  return new Promise((resolve, reject) => {
    let t;
    try {
      t = db.transaction(
        block ? ["epochs", "blocks"] : ["epochs"],
        "readwrite",
        { durability: "strict" },
      );
    } catch (error) {
      reject(new Error("当前浏览器不支持可靠本机保存"));
      return;
    }
    t.objectStore("epochs").put(epoch);
    if (block) t.objectStore("blocks").put(block);
    t.oncomplete = () => resolve();
    t.onerror = () => reject(t.error);
    t.onabort = () => reject(t.error || new Error("本机保存失败"));
  });
}
