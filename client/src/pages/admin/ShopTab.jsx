import { useCallback, useEffect, useRef, useState } from "react";
import ProductArt, { ART_OPTIONS } from "../../components/ProductArt";
import {
  createProduct,
  deleteProduct,
  downloadImportTemplate,
  importProducts,
  listAdminProducts,
  updateProduct
} from "../../lib/adminApi";
import { can, P } from "../../lib/permissions";
import { money } from "../../lib/ptFormat";
import Modal, { Field } from "./Modal";
import { ExportButton, SortHeader } from "./TableTools";

const PAGE_SIZE = 12;
const LOW_STOCK = 5;

const STATUS = {
  ACTIVE: { label: "Đang bán", tone: "is-ok" },
  INACTIVE: { label: "Đang ẩn", tone: "is-muted" },
  DRAFT: { label: "Bản nháp", tone: "is-muted" }
};
const GROUPS = { GYM: "Gym", YOGA: "Yoga" };
const CATEGORIES = ["Phụ kiện", "Trang phục", "Túi tập", "Dinh dưỡng", "Dụng cụ"];

const emptyProduct = {
  name: "",
  sku: "",
  category_name: "Phụ kiện",
  activity_type: "GYM",
  description: "",
  price: 199000,
  stock_quantity: 20,
  status: "ACTIVE",
  badge: "",
  art: "bag"
};

const toPayload = (form) => ({
  name: form.name,
  sku: form.sku || null,
  category_name: form.category_name,
  activity_type: form.activity_type,
  description: form.description || null,
  price: Number(form.price),
  stock_quantity: Number(form.stock_quantity),
  status: form.status,
  badge: form.badge || null,
  art: form.art || null,
  // Khoá phiên bản: người khác sửa trước thì máy chủ trả 409 thay vì ghi đè.
  row_version: form.row_version ?? null
});

function ImportResult({ result, onClose }) {
  return (
    <Modal
      title="Kết quả nhập sản phẩm"
      onClose={onClose}
      footer={<div className="adm-actions"><button type="button" className="adm-btn" onClick={onClose}>Đóng</button></div>}
    >
      <p className="adm-note">
        Thêm mới <b>{result.created}</b> · cập nhật <b>{result.updated}</b> · lỗi <b>{result.errors.length}</b> dòng.
      </p>
      {result.errors.length ? (
        <ul className="adm-import-errors">
          {result.errors.map((item) => (
            <li key={`${item.row}-${item.message}`}><b>Dòng {item.row}:</b> {item.message}</li>
          ))}
        </ul>
      ) : null}
    </Modal>
  );
}

function ProductForm({ initial, onSubmit, onClose }) {
  const editing = Boolean(initial?.id);
  const [form, setForm] = useState(() =>
    editing
      ? {
          ...emptyProduct,
          ...initial,
          category_name: initial.category_name || "",
          activity_type: initial.activity_type || "GYM",
          description: initial.description || "",
          badge: initial.badge || "",
          art: initial.art || "bag"
        }
      : emptyProduct
  );
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);
  const set = (key) => (event) => setForm((current) => ({ ...current, [key]: event.target.value }));

  const submit = async (event) => {
    event.preventDefault();
    setSaving(true);
    setError("");
    try {
      await onSubmit(toPayload(form));
    } catch (err) {
      setError(err.message || "Không lưu được sản phẩm.");
      setSaving(false);
    }
  };

  return (
    <Modal
      title={editing ? `Sửa sản phẩm · ${initial.name}` : "Thêm sản phẩm"}
      onClose={onClose}
      footer={
        <>
          {error ? <p className="adm-error">{error}</p> : <span />}
          <div className="adm-actions">
            <button type="button" className="adm-btn is-ghost" onClick={onClose}>Huỷ</button>
            <button type="submit" form="admProductForm" className="adm-btn" disabled={saving}>
              {saving ? "Đang lưu…" : editing ? "Lưu thay đổi" : "Thêm sản phẩm"}
            </button>
          </div>
        </>
      }
    >
      <form id="admProductForm" className="adm-form" onSubmit={submit}>
        <Field label="Tên sản phẩm" wide>
          <input value={form.name} onChange={set("name")} required maxLength={180} placeholder="Găng tay Grip Pro" autoFocus={!editing} />
        </Field>
        <Field label="Nhóm">
          <select value={form.activity_type} onChange={set("activity_type")}>
            {Object.entries(GROUPS).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
          </select>
        </Field>
        <Field label="Danh mục" hint="Chọn sẵn hoặc gõ tên danh mục mới.">
          <input value={form.category_name} onChange={set("category_name")} required maxLength={100} list="admProductCategories" />
          <datalist id="admProductCategories">
            {CATEGORIES.map((name) => <option key={name} value={name} />)}
          </datalist>
        </Field>
        <Field label="Giá bán (đ)">
          <input type="number" min="0" step="1000" value={form.price} onChange={set("price")} required />
        </Field>
        <Field label="Tồn kho" hint={editing && initial.reserved_quantity ? `${initial.reserved_quantity} sản phẩm đang giữ cho đơn hàng.` : undefined}>
          <input type="number" min={editing ? initial.reserved_quantity : 0} step="1" value={form.stock_quantity} onChange={set("stock_quantity")} required />
        </Field>
        <Field label="Mã SKU" hint={editing ? undefined : "Bỏ trống để hệ thống tự sinh."}>
          <input value={form.sku} onChange={(event) => setForm((current) => ({ ...current, sku: event.target.value.toUpperCase() }))} maxLength={40} pattern="[A-Z0-9][A-Z0-9_\-]{1,39}" placeholder="GYM-GLOVES-02" />
        </Field>
        <Field label="Trạng thái">
          <select value={form.status} onChange={set("status")}>
            {Object.entries(STATUS).map(([value, item]) => <option key={value} value={value}>{item.label}</option>)}
          </select>
        </Field>
        <Field label="Hình minh hoạ">
          <div className="adm-inline">
            <select value={form.art} onChange={set("art")}>
              {ART_OPTIONS.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
            </select>
            <span className="adm-art"><ProductArt type={form.art} /></span>
          </div>
        </Field>
        <Field label="Nhãn nổi bật" hint="Ví dụ: Mới, Bán chạy. Bỏ trống nếu không cần.">
          <input value={form.badge} onChange={set("badge")} maxLength={40} />
        </Field>
        <Field label="Mô tả ngắn" wide>
          <textarea rows={2} value={form.description} onChange={set("description")} maxLength={2000} placeholder="Da microfiber · Đệm gel chống trượt" />
        </Field>
      </form>
    </Modal>
  );
}

export default function ShopTab({ notify, onChange, user }) {
  const manage = can(user, P.PRODUCTS_MANAGE);
  const fileRef = useRef(null);
  const [sort, setSort] = useState("");
  const [importing, setImporting] = useState(false);
  const [imported, setImported] = useState(null);
  const [search, setSearch] = useState("");
  const [query, setQuery] = useState("");
  const [group, setGroup] = useState("");
  const [status, setStatus] = useState("");
  const [page, setPage] = useState(1);
  const [data, setData] = useState({ items: [], total: 0 });
  const [editing, setEditing] = useState(null);

  const load = useCallback(() => {
    listAdminProducts({ search: query, activity_type: group, status, sort, page, page_size: PAGE_SIZE })
      .then(setData)
      .catch((error) => notify(error.message || "Không tải được danh sách sản phẩm."));
  }, [query, group, status, sort, page, notify]);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      setQuery(search.trim());
      setPage(1);
    }, 300);
    return () => window.clearTimeout(timer);
  }, [search]);

  const pages = Math.max(1, Math.ceil(data.total / PAGE_SIZE));
  const refresh = () => {
    load();
    onChange();
  };

  const save = async (payload) => {
    if (editing?.id) {
      await updateProduct(editing.id, payload);
      notify("Đã cập nhật sản phẩm.");
    } else {
      await createProduct(payload);
      notify(payload.status === "ACTIVE" ? "Đã thêm sản phẩm, khách thấy ngay trên trang Sản phẩm." : "Đã thêm sản phẩm (chưa hiển thị cho khách).");
    }
    setEditing(null);
    refresh();
  };

  const toggle = async (product) => {
    const next = product.status === "ACTIVE" ? "INACTIVE" : "ACTIVE";
    try {
      await updateProduct(product.id, toPayload({ ...product, status: next }));
      notify(next === "ACTIVE" ? "Đã mở bán sản phẩm." : "Đã ẩn sản phẩm khỏi cửa hàng.");
      refresh();
    } catch (error) {
      notify(error.message || "Không cập nhật được sản phẩm.");
    }
  };

  const handleImport = async (event) => {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) return;
    setImporting(true);
    try {
      setImported(await importProducts(file));
      refresh();
    } catch (error) {
      notify(error.message || "Không nhập được file.");
    } finally {
      setImporting(false);
    }
  };

  const template = (format) =>
    downloadImportTemplate(format).catch((error) => notify(error.message || "Không tải được file mẫu."));

  const remove = async (product) => {
    if (!window.confirm(`Xoá sản phẩm ${product.name}? Sản phẩm sẽ biến mất khỏi cửa hàng; đơn hàng cũ không bị ảnh hưởng.`)) return;
    try {
      await deleteProduct(product.id);
      notify("Đã xoá sản phẩm.");
      refresh();
    } catch (error) {
      notify(error.message || "Không xoá được sản phẩm.");
    }
  };

  return (
    <div className="adm-panel">
      <div className="adm-toolbar">
        <input
          className="adm-search"
          type="search"
          value={search}
          onChange={(event) => setSearch(event.target.value)}
          placeholder="Tìm tên sản phẩm, SKU, danh mục…"
          aria-label="Tìm sản phẩm"
        />
        <select value={group} onChange={(event) => { setGroup(event.target.value); setPage(1); }} aria-label="Lọc nhóm">
          <option value="">Gym và Yoga</option>
          {Object.entries(GROUPS).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
        </select>
        <select value={status} onChange={(event) => { setStatus(event.target.value); setPage(1); }} aria-label="Lọc trạng thái">
          <option value="">Mọi trạng thái</option>
          {Object.entries(STATUS).map(([value, item]) => <option key={value} value={value}>{item.label}</option>)}
        </select>
        <div className="adm-toolbar-group">
          {can(user, P.REPORTS_EXPORT) ? (
            <ExportButton report="products" filters={{ search: query, activity_type: group, status, sort }} notify={notify} />
          ) : null}
          {manage ? (
            <>
              <input ref={fileRef} type="file" accept=".xlsx,.csv" hidden onChange={handleImport} />
              <button type="button" className="adm-btn is-ghost" disabled={importing} onClick={() => fileRef.current?.click()}>
                {importing ? "Đang nhập…" : "Nhập Excel/CSV"}
              </button>
              <button type="button" className="adm-link" onClick={() => template("xlsx")}>File mẫu</button>
              <button type="button" className="adm-btn" onClick={() => setEditing({})}>+ Thêm sản phẩm</button>
            </>
          ) : null}
        </div>
      </div>

      <div className="adm-card">
        <div className="adm-table-wrap">
          <table className="adm-table">
            <thead>
              <tr>
                <SortHeader label="Sản phẩm" column="name" sort={sort} onSort={(next) => { setSort(next); setPage(1); }} />
                <th>Danh mục</th>
                <SortHeader label="Giá bán" column="price" numeric sort={sort} onSort={(next) => { setSort(next); setPage(1); }} />
                <SortHeader label="Tồn kho" column="stock_quantity" numeric sort={sort} onSort={(next) => { setSort(next); setPage(1); }} />
                <th>Trạng thái</th>
                <th aria-label="Thao tác" />
              </tr>
            </thead>
            <tbody>
              {data.items.length === 0 ? (
                <tr><td colSpan={6} className="adm-empty">Không có sản phẩm phù hợp.</td></tr>
              ) : (
                data.items.map((product) => {
                  const state = STATUS[product.status] || { label: product.status, tone: "" };
                  const available = product.stock_quantity - product.reserved_quantity;
                  return (
                    <tr key={product.id}>
                      <td>
                        <div className="adm-product">
                          <span className="adm-art"><ProductArt type={product.art} /></span>
                          <div>
                            <strong>{product.name}</strong>
                            <small>{product.sku}{product.badge ? ` · ${product.badge}` : ""}</small>
                          </div>
                        </div>
                      </td>
                      <td>
                        <span>{product.category_name || "—"}</span>
                        <small>{GROUPS[product.activity_type] || "—"}</small>
                      </td>
                      <td className="is-num"><b>{money(product.price)}</b></td>
                      <td className="is-num">
                        <span>{product.stock_quantity}</span>
                        {available <= 0 ? <small className="adm-warn">Hết hàng</small> : available <= LOW_STOCK ? <small className="adm-warn">Sắp hết</small> : null}
                        {product.reserved_quantity ? <small>{product.reserved_quantity} đang giữ</small> : null}
                      </td>
                      <td><span className={"adm-badge " + state.tone}>{state.label}</span></td>
                      <td className="adm-row-actions">
                        {manage ? (
                          <>
                            <button type="button" onClick={() => setEditing(product)}>Sửa</button>
                            <button type="button" onClick={() => toggle(product)}>{product.status === "ACTIVE" ? "Ẩn" : "Mở bán"}</button>
                            <button type="button" className="is-danger" onClick={() => remove(product)}>Xoá</button>
                          </>
                        ) : null}
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
        <div className="adm-pager">
          <span>{data.total} sản phẩm</span>
          <button type="button" disabled={page <= 1} onClick={() => setPage((value) => value - 1)}>← Trước</button>
          <span>Trang {page}/{pages}</span>
          <button type="button" disabled={page >= pages} onClick={() => setPage((value) => value + 1)}>Sau →</button>
        </div>
      </div>

      {editing ? <ProductForm initial={editing} onSubmit={save} onClose={() => setEditing(null)} /> : null}
      {imported ? <ImportResult result={imported} onClose={() => setImported(null)} /> : null}
    </div>
  );
}
