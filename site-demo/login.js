const DEMO_EMAIL = "usuario@demo.com";
const DEMO_PASSWORD = "demo123";
const SESSION_KEY = "autotask-demo-session";
const PRODUCTS_KEY = "autotask-demo-products";

const parameters = new URLSearchParams(window.location.search);
if (parameters.get("reset") === "1") {
    localStorage.removeItem(SESSION_KEY);
    localStorage.removeItem(PRODUCTS_KEY);
    history.replaceState({}, "", "index.html");
}

const form = document.querySelector("#login-form");
const emailInput = document.querySelector("#email");
const message = document.querySelector("#login-message");

function focusLogin() {
    window.requestAnimationFrame(() => {
        emailInput.focus({ preventScroll: true });
    });
}

window.addEventListener("focus", focusLogin);
document.addEventListener("visibilitychange", () => {
    if (!document.hidden) {
        focusLogin();
    }
});
focusLogin();

form.addEventListener("submit", (event) => {
    event.preventDefault();

    const data = new FormData(form);
    const email = String(data.get("email") ?? "").trim();
    const password = String(data.get("password") ?? "");

    if (email !== DEMO_EMAIL || password !== DEMO_PASSWORD) {
        message.textContent = "Credenciais inválidas para o ambiente de demonstração.";
        message.className = "form-message form-message--error";
        focusLogin();
        return;
    }

    message.textContent = "Acesso autorizado. Redirecionando...";
    message.className = "form-message form-message--success";
    localStorage.setItem(SESSION_KEY, "active");

    window.setTimeout(() => {
        window.location.replace("produtos.html");
    }, 120);
});
