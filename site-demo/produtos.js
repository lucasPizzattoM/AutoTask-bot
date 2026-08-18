const STORAGE_KEY = "autotask-demo-products";
const SESSION_KEY = "autotask-demo-session";
const PRODUCT_TITLE = "AutoTask — Produtos";

if (localStorage.getItem(SESSION_KEY) !== "active") {
    window.location.replace("index.html");
}

const form = document.querySelector("#product-form");
const codeInput = document.querySelector("#codigo");
const message = document.querySelector("#product-message");
const tableBody = document.querySelector("#products-table-body");
const emptyState = document.querySelector("#empty-state");
const countBadge = document.querySelector("#product-count");
const statusPill = document.querySelector("#status-pill");
const clearButton = document.querySelector("#clear-products");
const logoutLink = document.querySelector("#logout-link");

function readProducts() {
    try {
        const value = JSON.parse(localStorage.getItem(STORAGE_KEY) ?? "[]");
        return Array.isArray(value) ? value : [];
    } catch {
        return [];
    }
}

function saveProducts(products) {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(products));
}

function formatMoney(value) {
    const number = Number(value);
    if (!Number.isFinite(number)) {
        return "—";
    }
    return number.toLocaleString("pt-BR", {
        style: "currency",
        currency: "BRL",
    });
}

function formatDate(value) {
    const date = new Date(value);
    return new Intl.DateTimeFormat("pt-BR", {
        dateStyle: "short",
        timeStyle: "medium",
    }).format(date);
}

function appendCell(row, value) {
    const cell = document.createElement("td");
    cell.textContent = value;
    row.appendChild(cell);
}

function focusProductCode(afterFocus = null) {
    window.requestAnimationFrame(() => {
        codeInput.focus({ preventScroll: true });
        window.requestAnimationFrame(() => {
            if (typeof afterFocus === "function") {
                afterFocus();
            }
        });
    });
}

function updateWindowTitle(count) {
    document.title = `${PRODUCT_TITLE} · ${count}`;
}

function renderProducts() {
    const products = readProducts();
    countBadge.textContent = String(products.length);
    tableBody.replaceChildren();
    emptyState.hidden = products.length > 0;

    for (const product of products.slice().reverse()) {
        const row = document.createElement("tr");
        appendCell(row, product.codigo);
        appendCell(row, product.marca);
        appendCell(row, product.tipo);
        appendCell(row, product.categoria);
        appendCell(row, formatMoney(product.preco_unitario));
        appendCell(row, formatMoney(product.custo));
        appendCell(row, product.obs || "Nenhuma");
        appendCell(row, formatDate(product.created_at));
        tableBody.appendChild(row);
    }

    return products.length;
}

window.addEventListener("focus", focusProductCode);
document.addEventListener("visibilitychange", () => {
    if (!document.hidden) {
        focusProductCode();
    }
});

form.addEventListener("submit", (event) => {
    event.preventDefault();

    if (!form.reportValidity()) {
        focusProductCode();
        return;
    }

    const product = Object.fromEntries(new FormData(form).entries());
    product.created_at = new Date().toISOString();

    const products = readProducts();
    products.push(product);
    saveProducts(products);

    message.textContent = `Produto ${product.codigo} cadastrado com sucesso.`;
    statusPill.textContent = `${products.length} registro(s) processado(s)`;
    statusPill.classList.add("status-pill--success");
    form.reset();
    const productCount = renderProducts();
    focusProductCode(() => updateWindowTitle(productCount));
});

clearButton.addEventListener("click", () => {
    localStorage.removeItem(STORAGE_KEY);
    message.textContent = "Dados locais removidos.";
    statusPill.textContent = "Aguardando automação";
    statusPill.classList.remove("status-pill--success");
    const productCount = renderProducts();
    focusProductCode(() => updateWindowTitle(productCount));
});

logoutLink.addEventListener("click", () => {
    localStorage.removeItem(SESSION_KEY);
});

const initialProductCount = renderProducts();
focusProductCode(() => updateWindowTitle(initialProductCount));
