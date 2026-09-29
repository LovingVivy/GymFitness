import { useEffect, useState } from "react";
import { ApiError, request } from "./api";

const SESSION_KEY = "ironix_demo_session";
const TOKEN_KEY = "ironix_token";
const AUTH_EVENT = "ironix:auth-changed";

const EXPERIENCE_LABELS = {
  BEGINNER: "Mới bắt đầu",
  BASIC: "Cơ bản",
  INTERMEDIATE: "Đã tập 6–18 tháng",
  ADVANCED: "Trên 18 tháng"
};

const GOAL_LABELS = {
  WEIGHT_LOSS: "Giảm mỡ",
  MUSCLE_GAIN: "Tăng cơ & sức mạnh",
  GENERAL_HEALTH: "Thể lực tổng quát",
  FLEXIBILITY: "Tăng độ linh hoạt"
};

const ACTIVITY_LABELS = { GYM: "Gym", YOGA: "Yoga" };

function emitChange() {
  window.dispatchEvent(new CustomEvent(AUTH_EVENT));
}

export function getCurrentUser() {
  try {
    return JSON.parse(localStorage.getItem(SESSION_KEY) || "null");
  } catch {
    return null;
  }
}

export function getToken() {
  return localStorage.getItem(TOKEN_KEY);
}

function periodLabel(membership) {
  if (membership.duration_months) {
    return membership.duration_months === 12 ? "12 tháng" : `${membership.duration_months} tháng`;
  }
  return membership.duration_days ? `${membership.duration_days} ngày` : "—";
}

/**
 * Map the API profile onto the shape the pages render.
 *
 * Everything here comes from the database; the client no longer invents
 * membership or body data.
 */
function normalizeProfile(profile) {
  const membership = profile.membership;

  return {
    id: profile.id,
    role: profile.role,
    email: profile.email,
    fullName: profile.full_name ?? "",
    phone: profile.phone ?? "",
    avatarUrl: profile.avatar_url ?? "",
    height: profile.height_cm,
    weight: profile.weight_kg,
    experienceCode: profile.experience_level,
    experience: EXPERIENCE_LABELS[profile.experience_level] ?? null,
    weeklySessions: profile.weekly_training_sessions,
    goalCode: profile.fitness_goal,
    goal: GOAL_LABELS[profile.fitness_goal] ?? null,
    memberCode: profile.member_code,
    homeBranch: profile.home_branch_name,
    joinedAt: profile.member_joined_at,
    createdAt: profile.created_at,
    lastLoginAt: profile.last_login_at,
    ptCredits: {
      purchased: profile.pt_credits?.purchased ?? 0,
      reserved: profile.pt_credits?.reserved ?? 0,
      used: profile.pt_credits?.used ?? 0,
      remaining: profile.pt_credits?.remaining ?? 0
    },
    membership: membership
      ? {
          status: membership.status,
          planCode: membership.plan_code,
          name: membership.plan_name,
          activityType: membership.activity_type,
          category: ACTIVITY_LABELS[membership.activity_type] ?? membership.activity_type,
          period: periodLabel(membership),
          price: membership.price,
          currency: membership.currency,
          startAt: membership.start_at,
          endAt: membership.end_at,
          daysRemaining: membership.days_remaining,
          totalDays: membership.total_days
        }
      : null
  };
}

function persistUser(user) {
  localStorage.setItem(SESSION_KEY, JSON.stringify(user));
  emitChange();
  return user;
}

function persistToken(token) {
  localStorage.setItem(TOKEN_KEY, token);
}

export async function refreshProfile() {
  const token = getToken();
  if (!token) return null;

  try {
    const profile = await request("/profile", { token });
    return persistUser(normalizeProfile(profile));
  } catch (error) {
    // Chỉ đăng xuất khi token thực sự không còn hợp lệ.
    if (error instanceof ApiError && error.status === 401) {
      logout();
      return null;
    }
    throw error;
  }
}

export async function login(email, password) {
  const data = await request("/auth/login", {
    method: "POST",
    body: { email, password }
  });
  persistToken(data.access_token);
  const profile = await refreshProfile();
  return profile ?? persistUser(normalizeProfile(data.user));
}

export async function signup({ fullName, email, phone, password }) {
  const data = await request("/auth/register", {
    method: "POST",
    body: { full_name: fullName, email, phone: phone || null, password }
  });
  persistToken(data.access_token);
  const profile = await refreshProfile();
  return profile ?? persistUser(normalizeProfile(data.user));
}

export async function updateProfile(patch) {
  const profile = await request("/profile", {
    method: "PATCH",
    body: patch,
    token: getToken()
  });
  return persistUser(normalizeProfile(profile));
}

export async function uploadAvatar(dataUrl) {
  const profile = await request("/profile/avatar", {
    method: "POST",
    body: { image: dataUrl },
    token: getToken()
  });
  return persistUser(normalizeProfile(profile));
}

export function listPlans() {
  return request("/plans");
}

/**
 * Đăng ký gói (kèm lượt PT nếu có): tạo subscription + một payment PENDING duy nhất.
 *
 * Gói được kích hoạt khi ngân hàng báo đã nhận tiền (webhook ở backend).
 * Trang gọi hàm này sẽ mở PaymentCheckout với `payment.id` trả về và chờ.
 */
export function createSubscription(planId, ptSessions = 0) {
  return request("/subscriptions", {
    method: "POST",
    body: { plan_id: planId, pt_sessions: ptSessions },
    token: getToken()
  });
}

export function updateCurrentUser(updates) {
  const current = getCurrentUser();
  if (!current) return null;
  return persistUser({ ...current, ...updates });
}

export function logout() {
  localStorage.removeItem(SESSION_KEY);
  localStorage.removeItem(TOKEN_KEY);
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

export function useToken() {
  const [token, setToken] = useState(getToken);
  useEffect(() => {
    const sync = () => setToken(getToken());
    window.addEventListener(AUTH_EVENT, sync);
    window.addEventListener("storage", sync);
    return () => {
      window.removeEventListener(AUTH_EVENT, sync);
      window.removeEventListener("storage", sync);
    };
  }, []);
  return token;
}
