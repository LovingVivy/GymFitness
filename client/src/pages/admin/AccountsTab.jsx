import { useCallback, useEffect, useState } from "react";
import { createUser, deleteUser, listUsers, resetPassword, updateUser } from "../../lib/adminApi";
import { can, P, ROLE_LABELS } from "../../lib/permissions";
import { formatDateTime, money } from "../../lib/ptFormat";
import Modal, { Field } from "./Modal";
import { ExportButton, SortHeader } from "./TableTools";

const PAGE_SIZE = 15;
const STAFF_ROLES = ["PT", "MANAGER", "ADMIN"];
const STATUS_LABELS = { ACTIVE: "Hoạt động", SUSPENDED: "Tạm khoá", INACTIVE: "Ngưng", PENDING: "Chờ duyệt" };
const STATUS_TONE = { ACTIVE: "is-ok", SUSPENDED: "is-warning", INACTIVE: "is-muted", PENDING: "is-muted" };
const SPECIALTIES = [
  ["GYM", "Gym"],
  ["YOGA", "Yoga"],
  ["MUSCLE_GAIN", "Tăng cơ"],
  ["WEIGHT_LOSS", "Giảm mỡ"],
  ["FLEXIBILITY", "Linh hoạt"],
  ["REHABILITATION", "Phục hồi"]
];

const emptyForm = {
  full_name: "",
  email: "",
  username: "",
  phone: "",
  password: "",
  role: "USER",
  status: "ACTIVE",
  hourly_rate: 200000,
  bio: "",
  specialties: ["GYM"]
};

function UserForm({ initial, onSubmit, onClose, roles }) {
  const editing = Boolean(initial?.id);
  const [form, setForm] = useState(() =>
    editing
      ? {
          ...emptyForm,
          ...initial,
          username: initial.username || "",
          phone: initial.phone || "",
          bio: initial.bio || "",
          hourly_rate: initial.hourly_rate ?? 200000
        }
      : emptyForm
  );
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const set = (key) => (event) => setForm((current) => ({ ...current, [key]: event.target.value }));

  const toggleSpecialty = (value) =>
    setForm((current) => ({
      ...current,
      specialties: current.specialties.includes(value)
        ? current.specialties.filter((item) => item !== value)
        : [...current.specialties, value]
    }));

  const submit = async (event) => {
    event.preventDefault();
    setSaving(true);
    setError("");
    const isTrainer = form.role === "PT";
    const payload = editing
      ? {
          full_name: form.full_name,
          email: form.email,
          username: form.username,
          phone: form.phone,
          status: form.status,
          ...(isTrainer ? { hourly_rate: Number(form.hourly_rate), bio: form.bio, specialties: form.specialties } : {})
        }
      : {
          full_name: form.full_name,
          email: form.email,
          username: form.username || null,
          phone: form.phone || null,
          password: form.password,
          role: form.role,
          ...(isTrainer ? { hourly_rate: Number(form.hourly_rate), bio: form.bio || null, specialties: form.specialties } : {})
        };
    try {
      await onSubmit(payload);
    } catch (err) {
      setError(err.message || "Không lưu được tài khoản.");
      setSaving(false);
    }
  };

  return (
    <Modal
      title={editing ? `Sửa tài khoản · ${initial.full_name || initial.email}` : "Thêm tài khoản"}
      onClose={onClose}
      footer={
        <>
          {error ? <p className="adm-error">{error}</p> : <span />}
          <div className="adm-actions">
            <button type="button" className="adm-btn is-ghost" onClick={onClose}>Huỷ</button>
            <button type="submit" form="admUserForm" className="adm-btn" disabled={saving}>
              {saving ? "Đang lưu…" : editing ? "Lưu thay đổi" : "Tạo tài khoản"}
            </button>
          </div>
        </>
      }
    >
      <form id="admUserForm" className="adm-form" onSubmit={submit}>
        {!editing ? (
          <Field label="Vai trò" wide>
            <div className="adm-segment">
              {roles.map((value) => (
                <button
                  key={value}
                  type="button"
                  className={form.role === value ? "is-active" : ""}
                  onClick={() => setForm((current) => ({ ...current, role: value }))}
                >
                  {ROLE_LABELS[value]}
                </button>
              ))}
            </div>
          </Field>
        ) : null}
        <Field label="Họ và tên"><input value={form.full_name} onChange={set("full_name")} required maxLength={150} /></Field>
        <Field label="Email"><input type="email" value={form.email} onChange={set("email")} required /></Field>
        <Field label="Tên đăng nhập" hint="Không bắt buộc. Chữ thường, số, dấu chấm, gạch dưới.">
          <input value={form.username} onChange={set("username")} pattern="[a-z0-9._]{3,50}" autoComplete="off" />
        </Field>
        <Field label="Số điện thoại"><input value={form.phone} onChange={set("phone")} maxLength={30} /></Field>
        {editing ? (
          <Field label="Trạng thái">
            <select value={form.status} onChange={set("status")}>
              <option value="ACTIVE">Hoạt động</option>
              <option value="SUSPENDED">Tạm khoá (không đăng nhập được)</option>
              <option value="INACTIVE">Ngưng hoạt động</option>
            </select>
          </Field>
        ) : (
          <Field label="Mật khẩu" hint="Tối thiểu 8 ký tự.">
            <input type="password" value={form.password} onChange={set("password")} required minLength={8} autoComplete="new-password" />
          </Field>
        )}

        {form.role === "PT" ? (
          <>
            <Field label="Chuyên môn" wide>
              <div className="adm-chips">
                {SPECIALTIES.map(([value, label]) => (
                  <button
                    key={value}
                    type="button"
                    className={form.specialties.includes(value) ? "is-active" : ""}
                    onClick={() => toggleSpecialty(value)}
                  >
                    {label}
                  </button>
                ))}
              </div>
            </Field>
            <Field label="Giá mỗi buổi (đ)">
              <input type="number" min="0" step="10000" value={form.hourly_rate} onChange={set("hourly_rate")} />
            </Field>
            <Field label="Giới thiệu" wide>
              <textarea rows={3} value={form.bio} onChange={set("bio")} maxLength={2000} />
            </Field>
          </>
        ) : null}
      </form>
    </Modal>
  );
}

function PasswordForm({ user, onSubmit, onClose }) {
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const submit = async (event) => {
    event.preventDefault();
    try {
      await onSubmit(password);
    } catch (err) {
      setError(err.message || "Không đặt lại được mật khẩu.");
    }
  };
  return (
    <Modal
      title={`Đặt lại mật khẩu · ${user.full_name || user.email}`}
      onClose={onClose}
      footer={
        <>
          {error ? <p className="adm-error">{error}</p> : <span />}
          <div className="adm-actions">
            <button type="button" className="adm-btn is-ghost" onClick={onClose}>Huỷ</button>
            <button type="submit" form="admPasswordForm" className="adm-btn">Đặt lại</button>
          </div>
        </>
      }
    >
      <form id="admPasswordForm" className="adm-form" onSubmit={submit}>
        <Field label="Mật khẩu mới" hint="Tối thiểu 8 ký tự. Tài khoản đang bị khoá do nhập sai cũng được mở khoá." wide>
          <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} required minLength={8} autoComplete="new-password" autoFocus />
        </Field>
      </form>
    </Modal>
  );
}

export default function AccountsTab({ notify, currentUserId, onChange, user: viewer }) {
  const [search, setSearch] = useState("");
  const [query, setQuery] = useState("");
  const [role, setRole] = useState("");
  const [status, setStatus] = useState("");
  const [sort, setSort] = useState("");
  const [page, setPage] = useState(1);
  const manageStaff = can(viewer, P.USERS_MANAGE_STAFF);
  const canManage = (target) =>
    STAFF_ROLES.includes(target.role) ? manageStaff : can(viewer, P.USERS_MANAGE_MEMBERS);
  const creatableRoles = manageStaff ? ["USER", "PT", "MANAGER", "ADMIN"] : ["USER"];
  const [data, setData] = useState({ items: [], total: 0 });
  const [editing, setEditing] = useState(null);
  const [resetting, setResetting] = useState(null);

  const load = useCallback(() => {
    listUsers({ search: query, role, status, sort, page, page_size: PAGE_SIZE })
      .then(setData)
      .catch((error) => notify(error.message || "Không tải được danh sách tài khoản."));
  }, [query, role, status, sort, page, notify]);

  useEffect(() => {
    load();
  }, [load]);

  // Gõ xong 300ms mới tìm để không gọi API theo từng phím.
  useEffect(() => {
    const timer = window.setTimeout(() => {
      setQuery(search.trim());
      setPage(1);
    }, 300);
    return () => window.clearTimeout(timer);
  }, [search]);

  const pages = Math.max(1, Math.ceil(data.total / PAGE_SIZE));

  const save = async (payload) => {
    if (editing?.id) {
      await updateUser(editing.id, payload);
      notify("Đã cập nhật tài khoản.");
    } else {
      const created = await createUser(payload);
      notify(`Đã tạo tài khoản ${created.member_code || created.employee_code || created.email}.`);
    }
    setEditing(null);
    load();
    onChange();
  };

  const remove = async (user) => {
    if (!window.confirm(`Xoá tài khoản ${user.full_name || user.email}? Lịch sử thanh toán vẫn được giữ, email và số điện thoại được giải phóng.`)) return;
    try {
      await deleteUser(user.id);
      notify("Đã xoá tài khoản.");
      load();
      onChange();
    } catch (error) {
      notify(error.message || "Không xoá được tài khoản.");
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
          placeholder="Tìm tên, email, số điện thoại, mã hội viên…"
          aria-label="Tìm tài khoản"
        />
        <select value={role} onChange={(event) => { setRole(event.target.value); setPage(1); }} aria-label="Lọc vai trò">
          <option value="">Mọi vai trò</option>
          {Object.entries(ROLE_LABELS).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
        </select>
        <select value={status} onChange={(event) => { setStatus(event.target.value); setPage(1); }} aria-label="Lọc trạng thái">
          <option value="">Mọi trạng thái</option>
          <option value="ACTIVE">Hoạt động</option>
          <option value="SUSPENDED">Tạm khoá</option>
          <option value="INACTIVE">Ngưng</option>
        </select>
        <div className="adm-toolbar-group">
          {can(viewer, P.REPORTS_EXPORT) ? (
            <ExportButton report="users" filters={{ search: query, role, status, sort }} notify={notify} />
          ) : null}
          {can(viewer, P.USERS_MANAGE_MEMBERS) ? (
            <button type="button" className="adm-btn" onClick={() => setEditing({})}>+ Thêm tài khoản</button>
          ) : null}
        </div>
      </div>

      <div className="adm-card">
        <div className="adm-table-wrap">
          <table className="adm-table">
            <thead>
              <tr>
                <SortHeader label="Tài khoản" column="full_name" sort={sort} onSort={(next) => { setSort(next); setPage(1); }} />
                <th>Vai trò</th>
                <th>Gói / chuyên môn</th>
                <th>Trạng thái</th>
                <SortHeader label="Đăng nhập gần nhất" column="last_login_at" first="desc" sort={sort} onSort={(next) => { setSort(next); setPage(1); }} />
                <th aria-label="Thao tác" />
              </tr>
            </thead>
            <tbody>
              {data.items.length === 0 ? (
                <tr><td colSpan={6} className="adm-empty">Không có tài khoản phù hợp.</td></tr>
              ) : (
                data.items.map((user) => (
                  <tr key={user.id}>
                    <td>
                      <strong>{user.full_name || "—"}</strong>
                      <small>{user.email}{user.username ? ` · @${user.username}` : ""}</small>
                      <small>{[user.member_code, user.employee_code, user.phone].filter(Boolean).join(" · ")}</small>
                    </td>
                    <td><span className="adm-tag">{ROLE_LABELS[user.role] || user.role}</span></td>
                    <td>
                      {user.role === "PT" ? (
                        <>
                          <span>{user.specialties.join(" · ") || "—"}</span>
                          <small>{money(user.hourly_rate)}/buổi</small>
                          {user.has_schedule ? null : (
                            <small className="adm-warn">Chưa khai lịch làm việc nên hội viên chưa thấy PT này</small>
                          )}
                        </>
                      ) : user.role === "USER" ? (
                        user.active_plan_name ? (
                          <>
                            <span>{user.active_plan_name}</span>
                            <small>đến {formatDateTime(user.active_plan_end_at)}</small>
                          </>
                        ) : <span className="adm-muted">Chưa có gói</span>
                      ) : <span className="adm-muted">—</span>}
                    </td>
                    <td>
                      <span className={"adm-badge " + (STATUS_TONE[user.status] || "")}>{STATUS_LABELS[user.status] || user.status}</span>
                      {user.locked ? <small className="adm-warn">Khoá tạm do nhập sai mật khẩu</small> : null}
                    </td>
                    <td><small>{user.last_login_at ? formatDateTime(user.last_login_at) : "Chưa đăng nhập"}</small></td>
                    <td className="adm-row-actions">
                      {canManage(user) ? (
                        <>
                          <button type="button" onClick={() => setEditing(user)}>Sửa</button>
                          <button type="button" onClick={() => setResetting(user)}>Mật khẩu</button>
                        </>
                      ) : null}
                      {user.id !== currentUserId && can(viewer, P.USERS_DELETE) ? (
                        <button type="button" className="is-danger" onClick={() => remove(user)}>Xoá</button>
                      ) : null}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
        <div className="adm-pager">
          <span>{data.total} tài khoản</span>
          <button type="button" disabled={page <= 1} onClick={() => setPage((value) => value - 1)}>← Trước</button>
          <span>Trang {page}/{pages}</span>
          <button type="button" disabled={page >= pages} onClick={() => setPage((value) => value + 1)}>Sau →</button>
        </div>
      </div>

      {editing ? <UserForm initial={editing} roles={creatableRoles} onSubmit={save} onClose={() => setEditing(null)} /> : null}
      {resetting ? (
        <PasswordForm
          user={resetting}
          onClose={() => setResetting(null)}
          onSubmit={async (password) => {
            await resetPassword(resetting.id, password);
            notify("Đã đặt lại mật khẩu.");
            setResetting(null);
          }}
        />
      ) : null}
    </div>
  );
}
