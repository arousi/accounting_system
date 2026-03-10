const screen = document.body.dataset.screen;

const state = {
    token: localStorage.getItem("accounting_token") || "",
    selectedProjectId: Number(document.body.dataset.projectId || 0) || null,
    selectedFiscalYearId: null,
    metadata: null,
    projects: [],
};

function apiFetch(url, options = {}) {
    const headers = { ...(options.headers || {}) };
    if (state.token) {
        headers.Authorization = `Bearer ${state.token}`;
    }
    if (options.body && !(options.body instanceof FormData) && !headers["Content-Type"]) {
        headers["Content-Type"] = "application/json";
    }
    return fetch(url, { ...options, headers });
}

async function apiJson(url, options = {}) {
    const response = await apiFetch(url, options);
    const contentType = response.headers.get("Content-Type") || "";
    const body = contentType.includes("application/json") ? await response.json() : null;
    return { response, body };
}

function readFilenameFromHeaders(response, fallbackName) {
    const header = response.headers.get("Content-Disposition") || "";
    const match = header.match(/filename\*=UTF-8''([^;]+)|filename=([^;]+)/i);
    if (!match) {
        return fallbackName;
    }
    return decodeURIComponent((match[1] || match[2] || fallbackName).replace(/"/g, "").trim());
}

async function downloadAuthorizedFile(url, fallbackName) {
    const response = await apiFetch(url);
    if (!response.ok) {
        let message = window.APP_TEXTS.load_failed;
        const contentType = response.headers.get("Content-Type") || "";
        if (contentType.includes("application/json")) {
            const payload = await response.json();
            message = payload?.error || message;
        }
        throw new Error(message);
    }
    const blob = await response.blob();
    const downloadUrl = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = downloadUrl;
    link.download = readFilenameFromHeaders(response, fallbackName);
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(downloadUrl);
}

function bindDownloadLink(elementId, urlBuilder, fallbackName) {
    const element = document.getElementById(elementId);
    if (!element) {
        return;
    }
    element.href = "#";
    element.onclick = async (event) => {
        event.preventDefault();
        try {
            await downloadAuthorizedFile(urlBuilder(), fallbackName);
        } catch (error) {
            alert(error.message || window.APP_TEXTS.load_failed);
        }
    };
}

function requireToken() {
    if (!state.token) {
        window.location.href = "/";
        return false;
    }
    return true;
}

function updateLocaleButtons() {
    document.querySelectorAll("[data-locale-switch]").forEach((button) => {
        button.addEventListener("click", async () => {
            await fetch(`/locale/${button.dataset.localeSwitch}`, { method: "POST" });
            window.location.reload();
        });
    });
}

async function loadSessionOrRedirect() {
    if (!requireToken()) {
        return null;
    }
    const { response, body } = await apiJson("/api/v1/auth/session");
    if (!response.ok || !body?.active) {
        localStorage.removeItem("accounting_token");
        state.token = "";
        window.location.href = "/";
        return null;
    }
    return body;
}

async function routeByOnboardingState() {
    const { response, body } = await apiJson("/api/v1/onboarding/status");
    if (!response.ok) {
        window.location.href = "/onboarding";
        return;
    }
    if (!body.onboarding_complete) {
        window.location.href = "/onboarding";
        return;
    }
    window.location.href = "/projects";
}

async function loadMetadata() {
    const { response, body } = await apiJson("/api/v1/metadata/accounting");
    if (response.ok) {
        state.metadata = body;
    }
    return body;
}

async function loadProjects() {
    const { response, body } = await apiJson("/api/v1/projects");
    if (!response.ok) {
        return [];
    }
    state.projects = body.items;
    return body.items;
}

function fillSelect(element, items, mapper, placeholder) {
    if (!element) {
        return;
    }
    element.innerHTML = "";
    if (placeholder) {
        const option = document.createElement("option");
        option.value = "";
        option.textContent = placeholder;
        element.appendChild(option);
    }
    items.forEach((item) => {
        const option = document.createElement("option");
        const mapped = mapper(item);
        option.value = mapped.value;
        option.textContent = mapped.label;
        element.appendChild(option);
    });
}

function currentLocaleLabel(item) {
    return document.body.dataset.locale === "ar" ? item.name_ar : item.name_en;
}

function renderRecordList(element, items, renderer, emptyText) {
    if (!element) {
        return;
    }
    element.innerHTML = items.length ? items.map(renderer).join("") : `<article class="record-card">${emptyText}</article>`;
}

function renderProjectCards(projects) {
    const projectList = document.getElementById("project-list");
    if (!projectList) {
        return;
    }
    projectList.innerHTML = projects.map((project) => {
        const readiness = project.readiness || {};
        const route = readiness.ready_for_finance ? `/projects/${project.id}/workspace` : `/projects/${project.id}/config`;
        const actionText = readiness.ready_for_finance ? window.APP_TEXTS.open_finance : window.APP_TEXTS.open_configuration;
        const badge = readiness.ready_for_finance ? window.APP_TEXTS.ready : window.APP_TEXTS.needs_setup;
        return `
            <li>
                <div class="project-item">
                    <div>
                        <strong>${project.code}</strong>
                        <div>${project.name_ar}</div>
                        <div>${project.name_en}</div>
                        <small>${project.currency_code} • ${badge}</small>
                    </div>
                    <a class="link-button ${readiness.ready_for_finance ? "" : "ghost-button"}" href="${route}">${actionText}</a>
                </div>
            </li>
        `;
    }).join("");
}

async function setupLoginScreen() {
    const form = document.getElementById("login-form");
    const statusBox = document.getElementById("login-status");
    form.addEventListener("submit", async (event) => {
        event.preventDefault();
        const { response, body } = await apiJson("/api/v1/auth/login", {
            method: "POST",
            body: JSON.stringify({
                email: document.getElementById("email").value,
                password: document.getElementById("password").value,
            }),
        });
        if (!response.ok) {
            statusBox.textContent = body?.error || "Login failed";
            return;
        }
        localStorage.setItem("accounting_token", body.token);
        state.token = body.token;
        await routeByOnboardingState();
    });
}

async function setupRegisterScreen() {
    const form = document.getElementById("register-form");
    const statusBox = document.getElementById("register-status");
    form.addEventListener("submit", async (event) => {
        event.preventDefault();
        const { response, body } = await apiJson("/api/v1/auth/register", {
            method: "POST",
            body: JSON.stringify({
                full_name: document.getElementById("register-full-name").value,
                email: document.getElementById("register-email").value,
                password: document.getElementById("register-password").value,
                preferred_locale: document.getElementById("register-locale").value,
            }),
        });
        if (!response.ok) {
            statusBox.textContent = body?.error || window.APP_TEXTS.load_failed;
            return;
        }
        localStorage.setItem("accounting_token", body.token);
        state.token = body.token;
        window.location.href = "/onboarding";
    });
}

async function setupOnboardingScreen() {
    const session = await loadSessionOrRedirect();
    if (!session) {
        return;
    }

    async function refreshCompanies() {
        const [companiesResult, onboardingResult] = await Promise.all([
            apiJson("/api/v1/companies"),
            apiJson("/api/v1/onboarding/status"),
        ]);
        const companies = companiesResult.body?.items || [];
        renderRecordList(
            document.getElementById("company-list"),
            companies,
            (item) => `<article class="record-card"><strong>${item.code}</strong><div>${item.name}</div><div class="record-meta">${window.APP_TEXTS.user_role}: ${item.membership?.role || "-"}</div></article>`,
            window.APP_TEXTS.active_company_required,
        );
        const finishLink = document.getElementById("onboarding-finish");
        if (onboardingResult.body?.onboarding_complete) {
            finishLink.classList.remove("ghost-button");
            finishLink.href = "/projects";
        } else {
            finishLink.classList.add("ghost-button");
            finishLink.href = "#";
            finishLink.onclick = (event) => {
                event.preventDefault();
                alert(window.APP_TEXTS.project_not_ready);
            };
        }
    }

    document.getElementById("company-form").addEventListener("submit", async (event) => {
        event.preventDefault();
        const { response, body } = await apiJson("/api/v1/companies", {
            method: "POST",
            body: JSON.stringify({
                code: document.getElementById("company-code").value,
                name: document.getElementById("company-name").value,
            }),
        });
        if (!response.ok) {
            alert(body?.error || window.APP_TEXTS.load_failed);
            return;
        }
        event.target.reset();
        await refreshCompanies();
    });

    document.getElementById("onboarding-project-form").addEventListener("submit", async (event) => {
        event.preventDefault();
        const year = new Date().getFullYear();
        const { response, body } = await apiJson("/api/v1/projects", {
            method: "POST",
            body: JSON.stringify({
                code: document.getElementById("onboarding-project-code").value,
                name_ar: document.getElementById("onboarding-project-name-ar").value,
                name_en: document.getElementById("onboarding-project-name-en").value,
                currency_code: document.getElementById("onboarding-project-currency").value,
                fiscal_year: {
                    code: String(year),
                    name: `Fiscal Year ${year}`,
                    start_date: `${year}-01-01`,
                    end_date: `${year}-12-31`,
                },
            }),
        });
        if (!response.ok) {
            alert(body?.error || window.APP_TEXTS.load_failed);
            return;
        }
        window.location.href = `/projects/${body.project.id}/config`;
    });

    await refreshCompanies();
}

async function setupProjectsScreen() {
    const session = await loadSessionOrRedirect();
    if (!session) {
        return;
    }
    if (!session.session?.active_company_id) {
        const onboarding = await apiJson("/api/v1/onboarding/status");
        if (!onboarding.body?.onboarding_complete) {
            window.location.href = "/onboarding";
            return;
        }
    }
    document.getElementById("projects-user-summary").textContent = `${session.user.full_name} • ${session.user.email}`;
    fillSelect(
        document.getElementById("company-switcher"),
        session.companies || [],
        (item) => ({ value: item.id, label: `${item.code} - ${item.name}` }),
    );
    if (session.session?.active_company_id) {
        document.getElementById("company-switcher").value = String(session.session.active_company_id);
    }
    document.getElementById("company-switcher").addEventListener("change", async (event) => {
        const companyId = Number(event.target.value);
        const { response, body } = await apiJson(`/api/v1/companies/${companyId}/switch`, { method: "POST" });
        if (!response.ok) {
            alert(body?.error || window.APP_TEXTS.load_failed);
            return;
        }
        window.location.reload();
    });
    bindDownloadLink("excel-export", () => "/api/v1/exports/projects.xlsx", "projects.xlsx");
    bindDownloadLink("pdf-export", () => "/api/v1/exports/projects.pdf", "projects.pdf");
    document.getElementById("logout-button").addEventListener("click", async () => {
        await apiFetch("/api/v1/auth/logout", { method: "POST" });
        localStorage.removeItem("accounting_token");
        window.location.href = "/";
    });
    document.getElementById("project-form").addEventListener("submit", async (event) => {
        event.preventDefault();
        const year = new Date().getFullYear();
        const { response, body } = await apiJson("/api/v1/projects", {
            method: "POST",
            body: JSON.stringify({
                code: document.getElementById("project-code").value,
                name_ar: document.getElementById("project-name-ar").value,
                name_en: document.getElementById("project-name-en").value,
                currency_code: document.getElementById("project-currency").value,
                fiscal_year: {
                    code: String(year),
                    name: `Fiscal Year ${year}`,
                    start_date: `${year}-01-01`,
                    end_date: `${year}-12-31`,
                },
            }),
        });
        if (!response.ok) {
            alert(body?.error || window.APP_TEXTS.load_failed);
            return;
        }
        window.location.href = `/projects/${body.project.id}/config`;
    });
    renderProjectCards(await loadProjects());
}

async function setupProjectConfigScreen() {
    const session = await loadSessionOrRedirect();
    if (!session || !state.selectedProjectId) {
        return;
    }
    await loadMetadata();
    const [projectResult, readinessResult, fiscalYearsResult, accountsResult, budgetsResult, usersResult, membershipsResult] = await Promise.all([
        apiJson(`/api/v1/projects/${state.selectedProjectId}`),
        apiJson(`/api/v1/projects/${state.selectedProjectId}/readiness`),
        apiJson(`/api/v1/projects/${state.selectedProjectId}/fiscal-years`),
        apiJson(`/api/v1/projects/${state.selectedProjectId}/accounts`),
        apiJson(`/api/v1/projects/${state.selectedProjectId}/budgets`),
        apiJson("/api/v1/users"),
        apiJson(`/api/v1/projects/${state.selectedProjectId}/memberships`),
    ]);
    if (!projectResult.response.ok) {
        window.location.href = "/projects";
        return;
    }
    const project = projectResult.body.project;
    const readiness = readinessResult.body.readiness;
    document.getElementById("config-project-title").textContent = `${project.code} - ${project.name_en}`;
    document.getElementById("config-readiness").textContent = readiness.ready_for_finance ? window.APP_TEXTS.ready : window.APP_TEXTS.project_not_ready;
    document.getElementById("go-workspace-link").href = `/projects/${state.selectedProjectId}/workspace`;
    fillSelect(document.getElementById("account-type"), state.metadata.account_types, (item) => ({ value: item.code, label: currentLocaleLabel(item) }), window.APP_TEXTS.account_type);
    fillSelect(document.getElementById("statement-type"), state.metadata.statement_types, (item) => ({ value: item.code, label: currentLocaleLabel(item) }), window.APP_TEXTS.statement_type);

    const renderAll = () => {
        const fiscalYears = fiscalYearsResult.body.items;
        const accounts = accountsResult.body.items;
        const budgets = budgetsResult.body.items;
        renderRecordList(document.getElementById("fiscal-year-list"), fiscalYears, (item) => `<article class="record-card"><strong>${item.code} - ${item.name}</strong><div class="record-meta">${item.start_date} → ${item.end_date}</div></article>`, window.APP_TEXTS.no_project_selected);
        renderRecordList(document.getElementById("account-list"), accounts, (item) => `<article class="record-card"><strong>${item.code} - ${item.name_ar}</strong><div>${item.name_en}</div><div class="record-meta">${item.account_type} | ${item.statement_type}</div></article>`, window.APP_TEXTS.no_project_selected);
        renderRecordList(document.getElementById("budget-list"), budgets, (item) => `<article class="record-card"><strong>${item.name}</strong><div class="record-meta">FY #${item.fiscal_year_id}</div><div class="record-meta">${window.APP_TEXTS.amount}: ${item.lines.reduce((sum, line) => sum + Number(line.amount || 0), 0).toFixed(2)}</div></article>`, window.APP_TEXTS.no_project_selected);
        fillSelect(document.getElementById("budget-fiscal-year"), fiscalYears, (item) => ({ value: item.id, label: `${item.code} - ${item.name}` }), window.APP_TEXTS.fiscal_year);
        fillSelect(document.getElementById("budget-account"), accounts, (item) => ({ value: item.id, label: `${item.code} - ${item.name_ar}` }), window.APP_TEXTS.budget_line_account);
        fillSelect(document.getElementById("membership-user"), usersResult.body.items, (item) => ({ value: item.id, label: `${item.full_name} - ${item.email}` }), window.APP_TEXTS.create_user);
        renderRecordList(document.getElementById("membership-list"), membershipsResult.body.items, (item) => `
            <article class="record-card">
                <strong>${item.user.full_name}</strong>
                <div>${item.user.email}</div>
                <div class="record-meta">${window.APP_TEXTS.user_role}: ${item.role}</div>
                <button type="button" class="ghost-button member-remove-button" data-membership-id="${item.id}">${window.APP_TEXTS.remove_member}</button>
            </article>
        `, window.APP_TEXTS.no_project_selected);
        document.querySelectorAll(".member-remove-button").forEach((button) => {
            button.onclick = async () => {
                const membershipId = Number(button.dataset.membershipId);
                const { response, body } = await apiJson(`/api/v1/projects/${state.selectedProjectId}/memberships/${membershipId}`, {
                    method: "DELETE",
                });
                if (!response.ok) {
                    alert(body?.error || window.APP_TEXTS.load_failed);
                    return;
                }
                membershipsResult.body.items = membershipsResult.body.items.filter((item) => item.id !== membershipId);
                renderAll();
            };
        });
    };
    renderAll();

    document.getElementById("fiscal-year-form").addEventListener("submit", async (event) => {
        event.preventDefault();
        const { response, body } = await apiJson(`/api/v1/projects/${state.selectedProjectId}/fiscal-years`, {
            method: "POST",
            body: JSON.stringify({
                code: document.getElementById("fiscal-year-code").value,
                name: document.getElementById("fiscal-year-name").value,
                start_date: document.getElementById("fiscal-year-start").value,
                end_date: document.getElementById("fiscal-year-end").value,
            }),
        });
        if (!response.ok) {
            alert(body?.error || window.APP_TEXTS.load_failed);
            return;
        }
        fiscalYearsResult.body.items.push(body.item);
        event.target.reset();
        renderAll();
    });

    document.getElementById("account-form").addEventListener("submit", async (event) => {
        event.preventDefault();
        const { response, body } = await apiJson(`/api/v1/projects/${state.selectedProjectId}/accounts`, {
            method: "POST",
            body: JSON.stringify({
                code: document.getElementById("account-code").value,
                name_ar: document.getElementById("account-name-ar").value,
                name_en: document.getElementById("account-name-en").value,
                account_type: document.getElementById("account-type").value,
                statement_type: document.getElementById("statement-type").value,
            }),
        });
        if (!response.ok) {
            alert(body?.error || window.APP_TEXTS.load_failed);
            return;
        }
        accountsResult.body.items.push(body.item);
        event.target.reset();
        renderAll();
    });

    document.getElementById("budget-form").addEventListener("submit", async (event) => {
        event.preventDefault();
        const { response, body } = await apiJson(`/api/v1/projects/${state.selectedProjectId}/budgets`, {
            method: "POST",
            body: JSON.stringify({
                name: document.getElementById("budget-name").value,
                fiscal_year_id: Number(document.getElementById("budget-fiscal-year").value),
                lines: [{ account_id: Number(document.getElementById("budget-account").value), amount: Number(document.getElementById("budget-amount").value) }],
            }),
        });
        if (!response.ok) {
            alert(body?.error || window.APP_TEXTS.load_failed);
            return;
        }
        budgetsResult.body.items.push(body.item);
        event.target.reset();
        renderAll();
    });

    document.getElementById("user-form").addEventListener("submit", async (event) => {
        event.preventDefault();
        const { response, body } = await apiJson("/api/v1/users", {
            method: "POST",
            body: JSON.stringify({
                full_name: document.getElementById("user-full-name").value,
                email: document.getElementById("user-email").value,
                password: document.getElementById("user-password").value,
                company_role: document.getElementById("user-company-role").value,
                department: document.getElementById("user-department").value,
                preferred_locale: document.getElementById("user-locale").value,
            }),
        });
        if (!response.ok) {
            alert(body?.error || window.APP_TEXTS.load_failed);
            return;
        }
        usersResult.body.items.push(body.item);
        event.target.reset();
        document.getElementById("user-company-role").value = "employee";
        document.getElementById("user-locale").value = "ar";
        renderAll();
    });

    document.getElementById("membership-form").addEventListener("submit", async (event) => {
        event.preventDefault();
        const { response, body } = await apiJson(`/api/v1/projects/${state.selectedProjectId}/memberships`, {
            method: "POST",
            body: JSON.stringify({
                user_id: Number(document.getElementById("membership-user").value),
                role: document.getElementById("membership-role").value,
            }),
        });
        if (!response.ok) {
            alert(body?.error || window.APP_TEXTS.load_failed);
            return;
        }
        const existingIndex = membershipsResult.body.items.findIndex((item) => item.id === body.item.id || item.user.id === body.item.user.id);
        if (existingIndex >= 0) {
            membershipsResult.body.items[existingIndex] = body.item;
        } else {
            membershipsResult.body.items.push(body.item);
        }
        event.target.reset();
        document.getElementById("membership-role").value = "member";
        renderAll();
    });
}

function setActiveWorkspaceTab(tabName) {
    document.querySelectorAll("[data-workspace-tab]").forEach((button) => {
        button.classList.toggle("is-active", button.dataset.workspaceTab === tabName);
    });
    document.querySelectorAll("[data-tab-panel]").forEach((panel) => {
        panel.classList.toggle("is-hidden", panel.dataset.tabPanel !== tabName);
    });
}

async function setupProjectWorkspaceScreen() {
    const session = await loadSessionOrRedirect();
    if (!session || !state.selectedProjectId) {
        return;
    }
    await loadMetadata();
    const projectList = await loadProjects();
    fillSelect(document.getElementById("project-switcher"), projectList, (item) => ({ value: item.id, label: `${item.code} - ${item.name_en}` }));
    document.getElementById("project-switcher").value = String(state.selectedProjectId);
    document.getElementById("project-switcher").addEventListener("change", (event) => {
        const selected = projectList.find((item) => item.id === Number(event.target.value));
        if (!selected) {
            return;
        }
        const route = selected.readiness?.ready_for_finance ? `/projects/${selected.id}/workspace` : `/projects/${selected.id}/config`;
        window.location.href = route;
    });

    const [{ body: projectBody }, { body: readinessBody }, { body: dashboardBody }, { body: fiscalYearsBody }, { body: accountsBody }] = await Promise.all([
        apiJson(`/api/v1/projects/${state.selectedProjectId}`),
        apiJson(`/api/v1/projects/${state.selectedProjectId}/readiness`),
        apiJson(`/api/v1/projects/${state.selectedProjectId}/dashboard`),
        apiJson(`/api/v1/projects/${state.selectedProjectId}/fiscal-years`),
        apiJson(`/api/v1/projects/${state.selectedProjectId}/accounts`),
    ]);
    const project = projectBody.project;
    const readiness = readinessBody.readiness;
    if (!readiness.ready_for_finance) {
        alert(window.APP_TEXTS.project_not_ready);
        window.location.href = `/projects/${state.selectedProjectId}/config`;
        return;
    }
    document.getElementById("workspace-project-title").textContent = `${project.code} - ${project.name_en}`;
    document.getElementById("workspace-readiness").textContent = window.APP_TEXTS.ready;
    document.getElementById("config-link").href = `/projects/${state.selectedProjectId}/config`;
    document.getElementById("metric-fiscal-years").textContent = dashboardBody.metrics.fiscal_year_count;
    document.getElementById("metric-accounts").textContent = dashboardBody.metrics.account_count;
    document.getElementById("metric-budgets").textContent = dashboardBody.metrics.budget_count;
    document.getElementById("metric-budget-total").textContent = Number(dashboardBody.metrics.budget_total).toFixed(2);

    const fiscalYears = fiscalYearsBody.items;
    const accounts = accountsBody.items;
    const eligibleTransferProjects = projectList.filter(
        (item) => item.id !== state.selectedProjectId && item.readiness?.has_fiscal_years && item.readiness?.has_accounts,
    );
    if (!fiscalYears.length) {
        alert(window.APP_TEXTS.fiscal_year_required);
        window.location.href = `/projects/${state.selectedProjectId}/config`;
        return;
    }
    state.selectedFiscalYearId = fiscalYears[0].id;
    fillSelect(document.getElementById("workspace-fiscal-year"), fiscalYears, (item) => ({ value: item.id, label: `${item.code} - ${item.name}` }));
    document.getElementById("workspace-fiscal-year").value = String(state.selectedFiscalYearId);
    document.getElementById("workspace-fiscal-year").addEventListener("change", async (event) => {
        state.selectedFiscalYearId = Number(event.target.value);
        updateExportLinks();
        await refreshWorkspaceData(accounts);
    });

    fillSelect(document.getElementById("journal-debit-account"), accounts, (item) => ({ value: item.id, label: `${item.code} - ${item.name_en}` }), window.APP_TEXTS.chart_of_accounts);
    fillSelect(document.getElementById("journal-credit-account"), accounts, (item) => ({ value: item.id, label: `${item.code} - ${item.name_en}` }), window.APP_TEXTS.chart_of_accounts);
    fillSelect(document.getElementById("ledger-account"), accounts, (item) => ({ value: item.id, label: `${item.code} - ${item.name_en}` }));
    fillSelect(document.getElementById("transfer-source-account"), accounts, (item) => ({ value: item.id, label: `${item.code} - ${item.name_en}` }), window.APP_TEXTS.source_account);
    document.getElementById("ledger-account").value = String(accounts[0]?.id || "");
    fillSelect(document.getElementById("transfer-destination-project"), eligibleTransferProjects, (item) => ({ value: item.id, label: `${item.code} - ${item.name_en}` }), window.APP_TEXTS.destination_project);

    function renderJournals(items) {
        renderRecordList(document.getElementById("journal-list"), items, (item) => `
            <article class="record-card">
                <strong>#${item.journal_number} • ${item.entry_date}</strong>
                <div>${item.description}</div>
                <div class="record-meta">D ${item.debit_total.toFixed(2)} | C ${item.credit_total.toFixed(2)}</div>
            </article>
        `, window.APP_TEXTS.no_project_selected);
    }

    function renderLedger(items) {
        renderRecordList(document.getElementById("ledger-list"), items, (item) => `
            <article class="record-card">
                <strong>${item.entry_date} • #${item.journal_number}</strong>
                <div>${item.description}</div>
                <div class="record-meta">D ${item.debit.toFixed(2)} | C ${item.credit.toFixed(2)} | Bal ${item.balance.toFixed(2)}</div>
            </article>
        `, window.APP_TEXTS.no_project_selected);
    }

    function renderTrialBalance(items, totals) {
        renderRecordList(document.getElementById("trial-balance-list"), items, (item) => `
            <article class="record-card">
                <strong>${item.account_code} - ${item.account_name_en}</strong>
                <div class="record-meta">D ${item.debit.toFixed(2)} | C ${item.credit.toFixed(2)} | Bal ${item.balance.toFixed(2)}</div>
            </article>
        `, window.APP_TEXTS.no_project_selected);
        document.getElementById("trial-balance-totals").textContent = `D ${Number(totals.debit).toFixed(2)} | C ${Number(totals.credit).toFixed(2)}`;
    }

    function renderTransfers(items) {
        renderRecordList(document.getElementById("transfer-list"), items, (item) => {
            const directionLabel = item.direction === "incoming" ? window.APP_TEXTS.incoming : window.APP_TEXTS.outgoing;
            return `
                <article class="record-card">
                    <strong>${item.transfer_date} • ${directionLabel}</strong>
                    <div>${item.source_project_code} → ${item.destination_project_code}</div>
                    <div>${item.description}</div>
                    <div class="record-meta">${window.APP_TEXTS.amount}: ${Number(item.total_amount).toFixed(2)}</div>
                </article>
            `;
        }, window.APP_TEXTS.no_transfers);
    }

    async function loadTransferDestinationContext() {
        const destinationProjectId = Number(document.getElementById("transfer-destination-project").value);
        if (!destinationProjectId) {
            fillSelect(document.getElementById("transfer-destination-fiscal-year"), [], (item) => ({ value: item.id, label: item.name }), window.APP_TEXTS.destination_fiscal_year);
            fillSelect(document.getElementById("transfer-destination-account"), [], (item) => ({ value: item.id, label: item.name_en }), window.APP_TEXTS.destination_account);
            return;
        }
        const [fiscalYearsResult, accountsResult] = await Promise.all([
            apiJson(`/api/v1/projects/${destinationProjectId}/fiscal-years`),
            apiJson(`/api/v1/projects/${destinationProjectId}/accounts`),
        ]);
        const destinationFiscalYears = fiscalYearsResult.body?.items || [];
        const destinationAccounts = accountsResult.body?.items || [];
        fillSelect(document.getElementById("transfer-destination-fiscal-year"), destinationFiscalYears, (item) => ({ value: item.id, label: `${item.code} - ${item.name}` }), window.APP_TEXTS.destination_fiscal_year);
        fillSelect(document.getElementById("transfer-destination-account"), destinationAccounts, (item) => ({ value: item.id, label: `${item.code} - ${item.name_en}` }), window.APP_TEXTS.destination_account);
    }

    async function refreshWorkspaceData(accountOptions) {
        const fiscalYearId = state.selectedFiscalYearId;
        const [journalsResult, trialBalanceResult, transfersResult] = await Promise.all([
            apiJson(`/api/v1/projects/${state.selectedProjectId}/journals?fiscal_year_id=${fiscalYearId}`),
            apiJson(`/api/v1/projects/${state.selectedProjectId}/trial-balance?fiscal_year_id=${fiscalYearId}`),
            apiJson(`/api/v1/projects/${state.selectedProjectId}/transfers?fiscal_year_id=${fiscalYearId}`),
        ]);
        renderJournals(journalsResult.body.items || []);
        renderTrialBalance(trialBalanceResult.body.items || [], trialBalanceResult.body.totals || { debit: 0, credit: 0 });
        renderTransfers(transfersResult.body.items || []);
        if (accountOptions.length) {
            const ledgerAccount = document.getElementById("ledger-account").value || String(accountOptions[0].id);
            const ledgerResult = await apiJson(`/api/v1/projects/${state.selectedProjectId}/ledger?fiscal_year_id=${fiscalYearId}&account_id=${ledgerAccount}`);
            renderLedger(ledgerResult.body.items || []);
        }
    }

    function updateExportLinks() {
        bindDownloadLink(
            "project-finance-excel",
            () => `/api/v1/projects/${state.selectedProjectId}/exports/finance.xlsx`,
            `${state.selectedProjectId}-finance.xlsx`,
        );
        bindDownloadLink(
            "project-finance-pdf",
            () => `/api/v1/projects/${state.selectedProjectId}/exports/finance.pdf`,
            `${state.selectedProjectId}-finance.pdf`,
        );
        bindDownloadLink(
            "fiscal-finance-excel",
            () => `/api/v1/projects/${state.selectedProjectId}/exports/finance.xlsx?fiscal_year_id=${state.selectedFiscalYearId}`,
            `${state.selectedProjectId}-${state.selectedFiscalYearId}-finance.xlsx`,
        );
        bindDownloadLink(
            "fiscal-finance-pdf",
            () => `/api/v1/projects/${state.selectedProjectId}/exports/finance.pdf?fiscal_year_id=${state.selectedFiscalYearId}`,
            `${state.selectedProjectId}-${state.selectedFiscalYearId}-finance.pdf`,
        );
    }

    document.getElementById("journal-form").addEventListener("submit", async (event) => {
        event.preventDefault();
        const debitAmount = Number(document.getElementById("journal-debit-amount").value);
        const creditAmount = Number(document.getElementById("journal-credit-amount").value);
        const { response, body } = await apiJson(`/api/v1/projects/${state.selectedProjectId}/journals`, {
            method: "POST",
            body: JSON.stringify({
                fiscal_year_id: state.selectedFiscalYearId,
                entry_date: document.getElementById("journal-date").value,
                description: document.getElementById("journal-description").value,
                lines: [
                    { account_id: Number(document.getElementById("journal-debit-account").value), description: document.getElementById("journal-description").value, debit: debitAmount, credit: 0 },
                    { account_id: Number(document.getElementById("journal-credit-account").value), description: document.getElementById("journal-description").value, debit: 0, credit: creditAmount },
                ],
            }),
        });
        if (!response.ok) {
            alert(body?.error || window.APP_TEXTS.load_failed);
            return;
        }
        event.target.reset();
        await refreshWorkspaceData(accounts);
    });

    document.getElementById("transfer-destination-project").addEventListener("change", async () => {
        await loadTransferDestinationContext();
    });

    document.getElementById("transfer-form").addEventListener("submit", async (event) => {
        event.preventDefault();
        const destinationProjectId = Number(document.getElementById("transfer-destination-project").value);
        if (!destinationProjectId) {
            alert(window.APP_TEXTS.destination_project_required);
            return;
        }
        const { response, body } = await apiJson(`/api/v1/projects/${state.selectedProjectId}/transfers`, {
            method: "POST",
            body: JSON.stringify({
                source_fiscal_year_id: state.selectedFiscalYearId,
                destination_project_id: destinationProjectId,
                destination_fiscal_year_id: Number(document.getElementById("transfer-destination-fiscal-year").value),
                transfer_date: document.getElementById("transfer-date").value,
                description: document.getElementById("transfer-description").value,
                lines: [
                    {
                        source_account_id: Number(document.getElementById("transfer-source-account").value),
                        destination_account_id: Number(document.getElementById("transfer-destination-account").value),
                        amount: Number(document.getElementById("transfer-amount").value),
                        description: document.getElementById("transfer-description").value,
                    },
                ],
            }),
        });
        if (!response.ok) {
            alert(body?.error || window.APP_TEXTS.load_failed);
            return;
        }
        event.target.reset();
        document.getElementById("transfer-destination-project").value = String(eligibleTransferProjects[0]?.id || "");
        await loadTransferDestinationContext();
        await refreshWorkspaceData(accounts);
    });

    document.getElementById("load-ledger-button").addEventListener("click", async () => {
        const accountId = document.getElementById("ledger-account").value;
        const { body } = await apiJson(`/api/v1/projects/${state.selectedProjectId}/ledger?fiscal_year_id=${state.selectedFiscalYearId}&account_id=${accountId}`);
        renderLedger(body.items || []);
    });

    document.querySelectorAll("[data-workspace-tab]").forEach((button) => {
        button.addEventListener("click", () => setActiveWorkspaceTab(button.dataset.workspaceTab));
    });

    updateExportLinks();
    if (eligibleTransferProjects.length) {
        document.getElementById("transfer-destination-project").value = String(eligibleTransferProjects[0].id);
        await loadTransferDestinationContext();
    }
    setActiveWorkspaceTab("journals");
    await refreshWorkspaceData(accounts);
}

function init() {
    updateLocaleButtons();
    if (screen === "login") {
        setupLoginScreen();
    } else if (screen === "register") {
        setupRegisterScreen();
    } else if (screen === "onboarding") {
        setupOnboardingScreen();
    } else if (screen === "projects") {
        setupProjectsScreen();
    } else if (screen === "project-config") {
        setupProjectConfigScreen();
    } else if (screen === "project-workspace") {
        setupProjectWorkspaceScreen();
    }
}

init();
