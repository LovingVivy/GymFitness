import { useEffect, useState } from "react";

const SESSION_KEY = "ironix_demo_session";
const USERS_KEY = "ironix_demo_users";
const AUTH_EVENT = "ironix:auth-changed";

export const DEMO_CREDENTIALS = {
  email: "demo@ironix.vn",
  password: "Demo@123"
};

const dateOnly = (date) => date.toISOString().slice(0, 10);

function createDemoUser() {
  const start = new Date();
  start.setDate(start.getDate() - 32);
  const end = new Date(start);
  end.setFullYear(end.getFullYear() + 1);

  return {
    id: "demo-user-001",
    role: "USER",
    fullName: "Nguyễn Minh Anh",
    email: DEMO_CREDENTIALS.email,
    phone: "090 123 4567",
    avatar: "",
    height: 172,
    weight: 66,
    experience: "Đã tập 6–18 tháng",
    weeklySessions: 4,
    goal: "Tăng cơ & sức mạnh",
    membership: {
      status: "ACTIVE",
      planKey: "gymYearly",
      name: "Gym theo năm",
      category: "Gym",
      period: "12 tháng",
      startDate: dateOnly(start),
      endDate: dateOnly(end),
      price: 4200000
    },
    ptCredits: { purchased: 12, reserved: 1, used: 3, remaining: 8 }
  };
}

function emitChange() {
  window.dispatchEvent(new CustomEvent(AUTH_EVENT));
}

function readUsers() {
  try {
    return JSON.parse(localStorage.getItem(USERS_KEY) || "[]");
  } catch {
    return [];
  }
}

export function getCurrentUser() {
  try {
    return JSON.parse(localStorage.getItem(SESSION_KEY) || "null");
  } catch {
    return null;
  }
}

export function login(email, password) {
  const normalizedEmail = email.trim().toLowerCase();
  let user = null;

  if (normalizedEmail === DEMO_CREDENTIALS.email && password === DEMO_CREDENTIALS.password) {
    user = createDemoUser();
  } else {
    const account = readUsers().find(
      (item) => item.email === normalizedEmail && item.password === password
    );
    if (account) {
      const { password: _password, ...safeAccount } = account;
      user = safeAccount;
    }
  }

  if (!user) return null;
  localStorage.setItem(SESSION_KEY, JSON.stringify(user));
  emitChange();
  return user;
}

export function signup({ fullName, email, phone, password }) {
  const normalizedEmail = email.trim().toLowerCase();
  const users = readUsers();
  if (normalizedEmail === DEMO_CREDENTIALS.email || users.some((item) => item.email === normalizedEmail)) {
    throw new Error("Email này đã được sử dụng.");
  }

  const user = {
    id: crypto.randomUUID(),
    role: "USER",
    fullName: fullName.trim(),
    email: normalizedEmail,
    phone: phone.trim(),
    avatar: "",
    height: null,
    weight: null,
    experience: "Mới bắt đầu",
    weeklySessions: 3,
    goal: "Thể lực tổng quát",
    membership: null,
    ptCredits: { purchased: 0, reserved: 0, used: 0, remaining: 0 }
  };

  users.push({ ...user, password });
  localStorage.setItem(USERS_KEY, JSON.stringify(users));
  localStorage.setItem(SESSION_KEY, JSON.stringify(user));
  emitChange();
  return user;
}

export function updateCurrentUser(updates) {
  const current = getCurrentUser();
  if (!current) return null;
  const updated = { ...current, ...updates };
  localStorage.setItem(SESSION_KEY, JSON.stringify(updated));
  emitChange();
  return updated;
}

export function purchaseMembership({ planKey, plan, ptSessions, profile }) {
  const current = getCurrentUser();
  if (!current) return null;

  const start = new Date();
  const end = new Date(start);
  if (plan.period === "12 tháng") end.setFullYear(end.getFullYear() + 1);
  else end.setMonth(end.getMonth() + 1);

  return updateCurrentUser({
    ...profile,
    membership: {
      status: "ACTIVE",
      planKey,
      name: plan.name,
      category: plan.category,
      period: plan.period,
      startDate: dateOnly(start),
      endDate: dateOnly(end),
      price: plan.price
    },
    ptCredits: { purchased: ptSessions, reserved: 0, used: 0, remaining: ptSessions }
  });
}

export function logout() {
  localStorage.removeItem(SESSION_KEY);
  emitChange();
}

export function useAuth() {
  const [user, setUser] = useState(getCurrentUser);
  useEffect(() => {
    const sync = () => setUser(getCurrentUser());
    window.addEventListener(AUTH_EVENT, sync);
    window.addEventListener("storage", sync);
    return () => {
      window.removeEventListener(AUTH_EVENT, sync);
      window.removeEventListener("storage", sync);
    };
  }, []);
  return user;
}
