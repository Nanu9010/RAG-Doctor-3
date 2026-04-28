/**
 * MedRAG – Auth Module
 * Handles: register, login, logout, session-guard, profile population
 */

/* ── Session Guard ──────────────────────────────────────────────────────── */
(function guardSession() {
  const isLoginPage = window.location.pathname.endsWith("index.html") || window.location.pathname === "/";
  const isDashboard  = window.location.pathname.includes("dashboard");

  if (isDashboard && !TokenStore.access) {
    window.location.href = "index.html";
  }
  if (isLoginPage && TokenStore.access) {
    window.location.href = "dashboard.html";
  }
})();

/* ── Tab Switch (login / register) ─────────────────────────────────────── */
function switchTab(tab) {
  document.querySelectorAll(".tab-btn").forEach((b, i) => {
    b.classList.toggle("active", (i === 0 && tab === "login") || (i === 1 && tab === "register"));
  });
  document.getElementById("loginForm").classList.toggle("active", tab === "login");
  document.getElementById("registerForm").classList.toggle("active", tab === "register");
  clearAlert();
}

function showAlert(message, type = "error") {
  const box = document.getElementById("alertBox");
  if (!box) return;
  box.textContent = message;
  box.className = `alert-box ${type}`;
}
function clearAlert() {
  const box = document.getElementById("alertBox");
  if (box) { box.className = "alert-box"; box.textContent = ""; }
}

function setLoading(btnId, loading) {
  const btn = document.getElementById(btnId);
  if (!btn) return;
  btn.disabled = loading;
  btn.classList.toggle("loading", loading);
}

/* ── Login ──────────────────────────────────────────────────────────────── */
async function handleLogin(e) {
  e.preventDefault();
  clearAlert();
  setLoading("loginBtn", true);

  const email    = document.getElementById("loginEmail").value.trim();
  const password = document.getElementById("loginPassword").value;

  try {
    const data = await apiPost("/auth/login/", { email, password });
    TokenStore.set(data.access, data.refresh);
    DoctorStore.set(data.doctor);
    window.location.href = "dashboard.html";
  } catch (err) {
    showAlert(err.message || "Login failed. Please check your credentials.");
  } finally {
    setLoading("loginBtn", false);
  }
}

/* ── Register ───────────────────────────────────────────────────────────── */
async function handleRegister(e) {
  e.preventDefault();
  clearAlert();

  const password  = document.getElementById("regPassword").value;
  const password2 = document.getElementById("regPassword2").value;

  if (password !== password2) {
    showAlert("Passwords do not match.");
    return;
  }
  if (password.length < 8) {
    showAlert("Password must be at least 8 characters.");
    return;
  }

  setLoading("registerBtn", true);

  const payload = {
    email:          document.getElementById("regEmail").value.trim(),
    first_name:     document.getElementById("regFirst").value.trim(),
    last_name:      document.getElementById("regLast").value.trim(),
    specialty:      document.getElementById("regSpecialty").value,
    license_number: document.getElementById("regLicense").value.trim(),
    hospital:       document.getElementById("regHospital").value.trim(),
    password,
    password2,
  };

  try {
    const data = await apiPost("/auth/register/", payload);
    TokenStore.set(data.access, data.refresh);
    DoctorStore.set(data.doctor);
    showAlert("Account created! Redirecting…", "success");
    setTimeout(() => { window.location.href = "dashboard.html"; }, 1200);
  } catch (err) {
    const errors = err.data || {};
    const messages = Object.entries(errors)
      .filter(([k]) => k !== "password2")
      .map(([k, v]) => `${k}: ${Array.isArray(v) ? v[0] : v}`)
      .join(" · ");
    showAlert(messages || err.message || "Registration failed.");
  } finally {
    setLoading("registerBtn", false);
  }
}

/* ── Logout ─────────────────────────────────────────────────────────────── */
async function handleLogout() {
  try {
    await apiPost("/auth/logout/", { refresh: TokenStore.refresh });
  } catch {
    // Ignore – clear locally regardless
  }
  TokenStore.clear();
  DoctorStore.clear();
  window.location.href = "index.html";
}

/* ── Dashboard Profile Population ───────────────────────────────────────── */
async function loadProfile() {
  let doctor = DoctorStore.get();

  if (!doctor) {
    try {
      doctor = await apiGet("/auth/profile/");
      DoctorStore.set(doctor);
    } catch {
      return;
    }
  }

  // Sidebar
  const nameEl      = document.getElementById("doctorName");
  const specEl      = document.getElementById("doctorSpecialty");
  const avatarEl    = document.getElementById("doctorAvatar");
  const badgeEl     = document.getElementById("specialtyBadge");
  const subtitleEl  = document.getElementById("chatSubtitle");

  if (nameEl)     nameEl.textContent     = doctor.full_name || "Doctor";
  if (specEl)     specEl.textContent     = doctor.specialty || "—";
  if (avatarEl)   avatarEl.textContent   = `${doctor.first_name?.[0] || "D"}${doctor.last_name?.[0] || "r"}`;
  if (badgeEl)    badgeEl.textContent    = doctor.specialty || "general";
  if (subtitleEl) subtitleEl.textContent = `Logged in as ${doctor.full_name}`;

  // Pre-select specialty filter to match doctor's specialty
  const sf = document.getElementById("specialtyFilter");
  if (sf && doctor.specialty) {
    const opt = sf.querySelector(`option[value="${doctor.specialty}"]`);
    if (opt) sf.value = doctor.specialty;
  }
}

/* ── Init on dashboard load ─────────────────────────────────────────────── */
if (document.querySelector(".app-shell")) {
  loadProfile();
}
