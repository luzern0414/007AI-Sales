import { useState } from "react";
import {
  Plus,
  ArrowUpRight,
  FileText,
  Upload,
  Package,
  Download,
} from "lucide-react";
import { useResource, post, api } from "../api";
import type { Product } from "../types";
import FilePreview,{FileGlyph} from '../components/FilePreview';
import {
  Empty,
  ErrorMessage,
  Loading,
  Modal,
  Form,
  values,
} from "../components/UI";

export default function Products() {
  const [modal, setModal] = useState(""),
    [selected, setSelected] = useState<Product | null>(null),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false),
    [draftId, setDraftId] = useState("");
  const [preview,setPreview]=useState('');
  const {
    value,
    loading,
    error: loadError,
    refresh,
  } = useResource<Product[]>("/products", 5000);
  async function upload(p: Product, files: FileList | null) {
    if (!files?.length) return;
    setError("");
    setBusy(true);
    try {
      const body = new FormData();
      body.append("file", files[0]);
      await api("/products/" + p.id + "/files", { method: "POST", body });
      refresh();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      <div className="page-heading">
        <div>
          <h1>产品库</h1>
        </div>
        {(
          <button className="button" onClick={() => {setDraftId("");setModal("new");}}>
            <Plus size={18} />
            新增产品
          </button>
        )}
      </div>
      <ErrorMessage message={error || loadError} />
      {loading && !value ? (
        <Loading />
      ) : (
        <div className="product-grid">
          {value?.map((p) => (
            <article className="product-card" key={p.id}>
              <div className="product-cover">
                <Package size={46} strokeWidth={1.1} />
                <span>
                  {p.published ? "已交付产品" : "待发布"}
                </span>
              </div>
              <div className="product-body">
                <h2>{p.name}</h2>
                <p className="product-summary">{p.summary}</p>
                <div className="product-actions">
                  {p.demo_url && (
                    <a
                      className="button secondary small"
                      href={p.demo_url}
                      target="_blank"
                      rel="noopener noreferrer"
                    >
                      查看系统
                      <ArrowUpRight size={17} />
                    </a>
                  )}
                  {p.files?.map((f) => (
                    <button
                      key={f.id}
                      className="text-button"
                      onClick={()=>setPreview(f.id)}
                    >
                      <FileGlyph name={f.name}/>
                      <span>{f.name}</span>
                      <Download size={16} />
                    </button>
                  ))}
                </div>
                {(
                  <div className="manage-actions">
                    <label className="text-button">
                      <Upload size={16} />
                      {busy ? "上传中" : "上传资料"}
                      <input
                        className="sr-only"
                        type="file"
                        accept=".pdf,.docx,.pptx,.md,.txt"
                        disabled={busy}
                        onChange={(e) => {
                          upload(p, e.target.files);
                          e.target.value = "";
                        }}
                      />
                    </label>
                    <button
                      className="text-button"
                      onClick={() => {
                        setSelected(p);
                        setModal("edit");
                      }}
                    >
                      编辑
                    </button>
                    <button
                      className="text-button"
                      onClick={() => {
                        setSelected(p);
                        setModal(p.published ? "unpublish" : "publish");
                      }}
                    >
                      {p.published ? "撤下" : "发布"}
                    </button>
                  </div>
                )}
              </div>
            </article>
          ))}
        </div>
      )}
      {!loading && !value?.length && (
        <Empty
          title="暂无产品"
          action="新增产品"
          onClick={() => {setDraftId("");setModal("new");}}
        />
      )}
      {(modal === "new" || modal === "edit") && (
        <Modal
          title={modal === "new" ? "新增产品" : "编辑产品"}
          onClose={() => setModal("")}
        >
          <Form
            onSubmit={async (f) => {
              const body: Record<string,string> = {...values(f),internal_notes:modal==="edit"?selected?.internal_notes||"":""};
              const fileInput=f.elements.namedItem("product_file") as HTMLInputElement;
              delete body.product_file;
              let product: Product;
              if(modal==="new") {
                if(draftId) product=await api("/products/"+draftId+"?version="+(value?.find(p=>p.id===draftId)?.version||1),{method:"PATCH",body:JSON.stringify(body)});
                else {product=await post<Product>("/products",body);setDraftId(product.id);}
              } else product=await api("/products/"+selected!.id+"?version="+selected!.version,{method:"PATCH",body:JSON.stringify(body)});
              try {
                if(fileInput.files?.[0]) {
                  const upload=new FormData();upload.append("file",fileInput.files[0]);
                  await api(`/products/${product.id}/files`,{method:"POST",body:upload});
                }
              } catch(e) {refresh();throw e;}
              setModal("");
              refresh();
            }}
          >
            <label>
              产品名称
              <input
                name="name"
                required
                maxLength={160}
                defaultValue={modal === "edit" ? selected?.name : ""}
                autoFocus
              />
            </label>
            <label>
              产品介绍
              <textarea
                name="summary"
                defaultValue={modal === "edit" ? selected?.summary : ""}
                maxLength={10000}
              />
            </label>
            <label>
              脱敏系统地址
              <input
                type="url"
                name="demo_url"
                defaultValue={modal === "edit" ? selected?.demo_url : ""}
              />
            </label>
            <label>产品资料<input name="product_file" type="file" accept=".pdf,.docx,.pptx,.md,.txt"/></label>
          </Form>
        </Modal>
      )}
      {preview&&<FilePreview id={preview} onClose={()=>setPreview('')} onChanged={refresh}/>}
      {(modal === "publish" || modal === "unpublish") && selected && (
        <Modal
          title={modal === "publish" ? "发布产品" : "撤下产品"}
          onClose={() => setModal("")}
        >
          <Form
            label={modal === "publish" ? "发布" : "撤下"}
            onSubmit={async () => {
              await post("/products/" + selected.id + "/" + modal, {
                version: selected.version,
                approved: true,
              });
              setModal("");
              refresh();
            }}
          >
            {modal === "publish" && (
              <label className="checkbox-label">
                <input type="checkbox" required />
                已核实落地情况、资料及演示脱敏
              </label>
            )}
          </Form>
        </Modal>
      )}
    </>
  );
}
