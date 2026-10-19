import { useCallback, useEffect, useState } from "react";
import { createPlan, deletePlan, listAdminPlans, updatePlan } from "../../lib/adminApi";
import { can, P } from "../../lib/permissions";
import { money } from "../../lib/ptFormat";
import Modal, { Field } from "./Modal";

const emptyPlan = {
  code: "",
  name: "",
  activity_type: "GYM",
  description: "",
  durationUnit: "months",
  durationValue: 1,
  price: 500000,
  is_active: true
};

const durationLabel = (plan) =>
  plan.duration_months
    ? plan.duration_months % 12 === 0
      ? `${plan.duration_months / 12} năm`
      : `${plan.duration_months} tháng`
    : `${plan.duration_days} ngày`;

function PlanForm({ initial, onSubmit, onClose }) {
  const editing = Boolean(initial?.id);
  const [form, setForm] = useState(() =>
    editing
      ? {
          ...emptyPlan,
          ...initial,
          description: initial.description || "",
          durationUnit: initial.duration_months ? "months" : "days",
          durationValue: initial.duration_months || initial.duration_days
        }
      : emptyPlan
  );
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);
  const set = (key) => (event) => setForm((current) => ({ ...current, [key]: event.target.value }));

  const submit = async (event) => {
    event.preventDefault();
    setSaving(true);
    setError("");
    const months = form.durationUnit === "months";
    try {
      await onSubmit({
        code: form.code,
        name: form.name,
        activity_type: form.activity_type,
        description: form.description || null,
        duration_months: months ? Number(form.durationValue) : null,
        duration_days: months ? null : Number(form.durationValue),
        price: Number(form.price),
        is_active: form.is_active,
        // Khoá phiên bản: người khác sửa trước thì máy chủ trả 409 thay vì ghi đè.
        row_version: editing ? initial.row_version : null
      });
    } catch (err) {
      setError(err.message || "Không lưu được gói tập.");
      setSaving(false);
    }
  };

  return (
    <Modal
      title={editing ? `Sửa gói · ${initial.name}` : "Thêm gói tập"}
      onClose={onClose}
      footer={
        <>
          {error ? <p className="adm-error">{error}</p> : <span />}
          <div className="adm-actions">
            <button type="button" className="adm-btn is-ghost" onClick={onClose}>Huỷ</button>
            <button type="submit" form="admPlanForm" className="adm-btn" disabled={saving}>
              {saving ? "Đang lưu…" : editing ? "Lưu thay đổi" : "Thêm gói"}
            </button>
          </div>
        </>
      }
    >
      <form id="admPlanForm" className="adm-form" onSubmit={submit}>
        <Field label="Tên gói"><input value={form.name} onChange={set("name")} required maxLength={150} placeholder="Gym 3 tháng" /></Field>
        <Field label="Mã gói" hint="Chữ in hoa, số, gạch dưới. Ví dụ GYM_3_MONTHS.">
          <input value={form.code} onChange={(e) => setForm((c) => ({ ...c, code: e.target.value.toUpperCase() }))} required pattern="[A-Z0-9_]{2,40}" />
        </Field>
        <Field label="Loại hình">
          <select value={form.activity_type} onChange={set("activity_type")}>
            <option value="GYM">Gym</option>
            <option value="YOGA">Yoga</option>
          </select>
        </Field>
        <Field label="Giá (đ)"><input type="number" min="0" step="1000" value={form.price} onChange={set("price")} required /></Field>
        <Field label="Thời hạn">
          <div className="adm-inline">
            <input type="number" min="1" max={form.durationUnit === "months" ? 60 : 3650} value={form.durationValue} onChange={set("durationValue")} required />
            <select value={form.durationUnit} onChange={set("durationUnit")} aria-label="Đơn vị thời hạn">
              <option value="months">tháng</option>
              <option value="days">ngày</option>
            </select>
          </div>
        </Field>
        <Field label="Trạng thái">
          <label className="adm-check">
            <input type="checkbox" checked={form.is_active} onChange={(e) => setForm((c) => ({ ...c, is_active: e.target.checked }))} />
            Đang mở bán
          </label>
        </Field>
        <Field label="Mô tả" wide>
          <textarea rows={3} value={form.description} onChange={set("description")} maxLength={2000} />
        </Field>
        {editing ? <p className="adm-muted adm-wide">Đổi giá chỉ áp dụng cho lượt mua mới; gói hội viên đã bán giữ nguyên.</p> : null}
      </form>
    </Modal>
  );
}

export default function PlansTab({ notify, user }) {
  const manage = can(user, P.PLANS_MANAGE);
  const [plans, setPlans] = useState([]);
  const [editing, setEditing] = useState(null);

  const load = useCallback(() => {
    listAdminPlans()
      .then(setPlans)
      .catch((error) => notify(error.message || "Không tải được gói tập."));
  }, [notify]);

  useEffect(() => {
    load();
  }, [load]);

  const save = async (payload) => {
    if (editing?.id) {
      await updatePlan(editing.id, payload);
      notify("Đã cập nhật gói tập.");
    } else {
      await createPlan(payload);
      notify("Đã thêm gói tập, hội viên có thể đăng ký ngay.");
    }
    setEditing(null);
    load();
  };

  const toggleActive = async (plan) => {
    try {
      await updatePlan(plan.id, {
        code: plan.code,
        name: plan.name,
        activity_type: plan.activity_type,
        description: plan.description,
        duration_months: plan.duration_months,
        duration_days: plan.duration_days,
        price: plan.price,
        is_active: !plan.is_active,
        row_version: plan.row_version
      });
      notify(plan.is_active ? "Đã ngừng bán gói." : "Đã mở bán lại gói.");
      load();
    } catch (error) {
      notify(error.message || "Không cập nhật được gói.");
    }
  };

  const remove = async (plan) => {
    const warning = plan.active_subscriptions
      ? ` ${plan.active_subscriptions} hội viên đang dùng gói này vẫn giữ quyền lợi tới hết hạn.`
      : "";
    if (!window.confirm(`Xoá gói ${plan.name}?${warning}`)) return;
    try {
      await deletePlan(plan.id);
      notify("Đã xoá gói tập.");
      load();
    } catch (error) {
      notify(error.message || "Không xoá được gói tập.");
    }
  };

  return (
    <div className="adm-panel">
      <div className="adm-toolbar">
        <span className="adm-muted">{plans.filter((plan) => plan.is_active).length}/{plans.length} gói đang mở bán</span>
        {manage ? (
          <button type="button" className="adm-btn" onClick={() => setEditing({})}>+ Thêm gói tập</button>
        ) : (
          <span className="adm-readonly">Chỉ quản trị viên được thêm, sửa hoặc xoá gói tập.</span>
        )}
      </div>

      <div className="adm-plan-grid">
        {plans.map((plan) => (
          <article key={plan.id} className={"adm-plan" + (plan.is_active ? "" : " is-off")}>
            <header>
              <span className="adm-tag">{plan.activity_type}</span>
              <span className={"adm-badge " + (plan.is_active ? "is-ok" : "is-muted")}>{plan.is_active ? "Đang bán" : "Ngừng bán"}</span>
            </header>
            <h3>{plan.name}</h3>
            <p className="adm-muted">{plan.code} · {durationLabel(plan)}</p>
            <strong className="adm-plan-price">{money(plan.price)}</strong>
            <dl>
              <div><dt>Đang dùng</dt><dd>{plan.active_subscriptions}</dd></div>
              <div><dt>Đã bán</dt><dd>{plan.total_sold}</dd></div>
            </dl>
            {manage ? (
              <div className="adm-row-actions">
                <button type="button" onClick={() => setEditing(plan)}>Sửa</button>
                <button type="button" onClick={() => toggleActive(plan)}>{plan.is_active ? "Ngừng bán" : "Mở bán"}</button>
                <button type="button" className="is-danger" onClick={() => remove(plan)}>Xoá</button>
              </div>
            ) : null}
          </article>
        ))}
      </div>

      {editing ? <PlanForm initial={editing} onSubmit={save} onClose={() => setEditing(null)} /> : null}
    </div>
  );
}
