const usersTbody = document.querySelector("#usersTable tbody");
const btnRefresh = document.getElementById("btnRefresh");
const btnSearch = document.getElementById("btnSearch");

async function fetchUsers(username=null){
  let url = "/api/users";
  if(username) url += "?username=" + encodeURIComponent(username);
  const res = await fetch(url);
  const j = await res.json();
  if (j.status !== "ok"){ alert("Failed to fetch users: " + j.message); return; }
  renderUsers(j.data || []);
}

function renderUsers(users){
  usersTbody.innerHTML = "";
  users.forEach(u => {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td>${u.id}</td>
      <td>${u.username}</td>
      <td>$${Number(u.balance||0).toFixed(2)}</td>
      <td>${u.broker||""}</td>
      <td>${u.is_frozen ? "Yes" : "No"}</td>
      <td class="actions">
        <button onclick="toggleFreeze(${u.id}, ${u.is_frozen})">${u.is_frozen ? "Unfreeze" : "Freeze"}</button>
        <button onclick="promptEdit(${u.id}, '${u.username}')">Edit</button>
        <button onclick="deleteUser(${u.id})" class="danger">Delete</button>
      </td>
    `;
    usersTbody.appendChild(tr);
  });
}

async function toggleFreeze(id, currentlyFrozen){
  const newVal = !currentlyFrozen;
  const res = await fetch("/api/users/" + id, {
    method: "PUT",
    headers: {"Content-Type":"application/json"},
    body: JSON.stringify({is_frozen: newVal})
  });
  const j = await res.json();
  if(j.status !== "ok") return alert("Error: " + j.message);
  fetchUsers();
}

async function promptEdit(id, username){
  const newBalance = prompt("Enter new balance (numbers only):");
  if(newBalance === null) return;
  const newBroker = prompt("Broker name (leave blank to keep):", "");
  const payload = { balance: parseFloat(newBalance) || 0.0 };
  if(newBroker !== null) payload.broker = newBroker;
  const res = await fetch("/api/users/" + id, {
    method: "PUT",
    headers: {"Content-Type":"application/json"},
    body: JSON.stringify(payload)
  });
  const j = await res.json();
  if(j.status !== "ok") return alert("Error: " + j.message);
  fetchUsers();
}

async function deleteUser(id){
  if(!confirm("Delete user id "+id+"? This cannot be undone.")) return;
  const res = await fetch("/api/users/" + id, { method: "DELETE" });
  const j = await res.json();
  if(j.status !== "ok") return alert("Error: " + j.message);
  fetchUsers();
}

// Create user
document.getElementById("createUserForm").addEventListener("submit", async e=>{
  e.preventDefault();
  const fd = new FormData(e.target);
  const payload = {
    username: fd.get("username"),
    password: fd.get("password"),
    balance: parseFloat(fd.get("balance") || 0),
    broker: fd.get("broker") || "",
    is_frozen: fd.get("is_frozen") === "true"
  };
  const res = await fetch("/api/users", { method:"POST", headers:{"Content-Type":"application/json"}, body: JSON.stringify(payload) });
  const j = await res.json();
  if(j.status !== "ok") return alert("Error: " + j.message);
  alert("User created.");
  e.target.reset();
  fetchUsers();
});

// Notifications
document.getElementById("notifyForm").addEventListener("submit", async e=>{
  e.preventDefault();
  const fd = new FormData(e.target);
  const payload = { user_id: fd.get("user_id"), message: fd.get("message") };
  const res = await fetch("/api/notifications", { method:"POST", headers:{"Content-Type":"application/json"}, body: JSON.stringify(payload) });
  const j = await res.json();
  if(j.status !== "ok") return alert("Error: " + j.message);
  alert("Notification sent.");
  e.target.reset();
});

// Reset password
document.getElementById("resetForm").addEventListener("submit", async e=>{
  e.preventDefault();
  const fd = new FormData(e.target);
  const payload = { new_password: fd.get("new_password")};
  const user_id = fd.get("user_id");
  const res = await fetch("/api/users/" + user_id + "/reset_password", { method:"POST", headers:{"Content-Type":"application/json"}, body: JSON.stringify(payload) });
  const j = await res.json();
  if(j.status !== "ok") return alert("Error: " + j.message);
  alert("Password reset successful.");
  e.target.reset();
});

btnRefresh.addEventListener("click", ()=>fetchUsers());
btnSearch.addEventListener("click", ()=> {
  const v = document.getElementById("searchUsername").value;
  fetchUsers(v || null);
});

// initial load
fetchUsers();
