import { useEffect, useMemo, useState } from "react";

const API_URL = import.meta.env.VITE_API_URL || "http://127.0.0.1:8000";
const emptyForm = { name: "", email: "", course: "", year: "1" };

async function request(path, options = {}) {
  const response = await fetch(`${API_URL}${path}`, {
    ...options,
    headers: { "Content-Type": "application/json", ...options.headers },
  });

  if (!response.ok) {
    let message = "Something went wrong. Please try again.";
    try {
      const data = await response.json();
      message = typeof data.detail === "string" ? data.detail : message;
    } catch {
      // Keep the friendly default message if the server did not return JSON.
    }
    throw new Error(message);
  }

  if (response.status === 204) return null;
  return response.json();
}

function getErrorMessage(error) {
  if (error instanceof TypeError) {
    return "Can't reach the backend yet. Make sure the FastAPI server is running.";
  }
  return error.message;
}

export default function App() {
  const [students, setStudents] = useState([]);
  const [form, setForm] = useState(emptyForm);
  const [editingId, setEditingId] = useState(null);
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  async function loadStudents() {
    setLoading(true);
    try {
      const data = await request("/api/students");
      setStudents(data);
      setError("");
    } catch (loadError) {
      setError(getErrorMessage(loadError));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadStudents();
  }, []);

  const visibleStudents = useMemo(() => {
    const term = search.trim().toLowerCase();
    if (!term) return students;
    return students.filter((student) =>
      [student.name, student.email, student.course].some((value) =>
        value.toLowerCase().includes(term),
      ),
    );
  }, [students, search]);

  function updateField(event) {
    const { name, value } = event.target;
    setForm((current) => ({ ...current, [name]: value }));
  }

  function resetForm() {
    setForm(emptyForm);
    setEditingId(null);
  }

  function startEditing(student) {
    setForm({
      name: student.name,
      email: student.email,
      course: student.course,
      year: String(student.year),
    });
    setEditingId(student.id);
    setNotice("");
    document.querySelector("#student-name")?.focus();
  }

  async function handleSubmit(event) {
    event.preventDefault();
    setSaving(true);
    setError("");
    setNotice("");

    const payload = { ...form, year: Number(form.year) };
    const path = editingId ? `/api/students/${editingId}` : "/api/students";

    try {
      await request(path, {
        method: editingId ? "PUT" : "POST",
        body: JSON.stringify(payload),
      });
      resetForm();
      setNotice(editingId ? "Student details updated." : "Student added.");
      await loadStudents();
    } catch (saveError) {
      setError(getErrorMessage(saveError));
    } finally {
      setSaving(false);
    }
  }

  async function removeStudent(student) {
    if (!window.confirm(`Delete ${student.name} from the student list?`)) return;
    setError("");
    setNotice("");
    try {
      await request(`/api/students/${student.id}`, { method: "DELETE" });
      if (editingId === student.id) resetForm();
      setNotice("Student deleted.");
      await loadStudents();
    } catch (deleteError) {
      setError(getErrorMessage(deleteError));
    }
  }

  return (
    <main className="page-shell">
      <header className="topbar">
        <a className="brand" href="#top" aria-label="Student Management home">
          <span className="brand-mark">S</span>
          <span>Campus<span className="brand-light">Desk</span></span>
        </a>
        <span className="topbar-label">STUDENT ADMINISTRATION</span>
      </header>

      <section className="intro" id="top">
        <div>
          <p className="eyebrow">STUDENT MANAGEMENT SYSTEM</p>
          <h1>Keep your campus<br /><span>in good order.</span></h1>
          <p className="intro-copy">A clear, simple place to manage student records.</p>
        </div>
        <div className="total-card" aria-live="polite">
          <span className="total-icon" aria-hidden="true">↗</span>
          <span className="total-label">TOTAL STUDENTS</span>
          <strong>{students.length.toString().padStart(2, "0")}</strong>
          <span className="total-caption">in your directory</span>
        </div>
      </section>

      {error && <div className="alert alert-error" role="alert">{error}</div>}
      {notice && <div className="alert alert-success" role="status">{notice}</div>}

      <section className="workspace">
        <aside className="form-panel">
          <div className="section-heading">
            <div>
              <p className="eyebrow">DIRECTORY TOOLS</p>
              <h2>{editingId ? "Edit student" : "Add a student"}</h2>
            </div>
            <span className="step-number">{editingId ? "02" : "01"}</span>
          </div>
          <p className="panel-copy">Enter the details below to {editingId ? "update this record" : "create a new record"}.</p>

          <form className="student-form" onSubmit={handleSubmit}>
            <label htmlFor="student-name">Full name</label>
            <input id="student-name" name="name" value={form.name} onChange={updateField} placeholder="e.g. Aisha Rao" minLength="2" maxLength="100" required />

            <label htmlFor="student-email">Email address</label>
            <input id="student-email" name="email" type="email" value={form.email} onChange={updateField} placeholder="aisha@example.com" maxLength="254" required />

            <label htmlFor="student-course">Course</label>
            <input id="student-course" name="course" value={form.course} onChange={updateField} placeholder="e.g. Computer Science" minLength="2" maxLength="100" required />

            <label htmlFor="student-year">Study year</label>
            <select id="student-year" name="year" value={form.year} onChange={updateField}>
              {[1, 2, 3, 4, 5, 6, 7, 8].map((year) => <option key={year} value={year}>Year {year}</option>)}
            </select>

            <div className="form-actions">
              <button className="button button-primary" type="submit" disabled={saving}>
                {saving ? "Saving…" : editingId ? "Save changes" : "Add student"}
                {!saving && <span aria-hidden="true">→</span>}
              </button>
              {editingId && <button className="button button-quiet" type="button" onClick={resetForm}>Cancel</button>}
            </div>
          </form>
          <div className="privacy-note"><span aria-hidden="true">●</span> Records are saved to your local SQL database.</div>
        </aside>

        <section className="directory-panel" aria-labelledby="directory-title">
          <div className="directory-heading">
            <div>
              <p className="eyebrow">CAMPUS RECORDS</p>
              <h2 id="directory-title">Student directory</h2>
              <p className="panel-copy">Browse and manage your student records.</p>
            </div>
            <span className="directory-count">{students.length} {students.length === 1 ? "RECORD" : "RECORDS"}</span>
          </div>

          <label className="search-box" htmlFor="student-search">
            <span aria-hidden="true">⌕</span>
            <input id="student-search" value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search name, email, or course" />
            {search && <button type="button" onClick={() => setSearch("")} aria-label="Clear search">×</button>}
          </label>

          <div className="table-wrap">
            <table>
              <thead><tr><th>STUDENT</th><th>COURSE</th><th>YEAR</th><th className="actions-column">ACTIONS</th></tr></thead>
              <tbody>
                {loading ? (
                  <tr><td colSpan="4" className="table-message">Loading student records…</td></tr>
                ) : visibleStudents.length === 0 ? (
                  <tr><td colSpan="4" className="table-message">{search ? "No matching students. Try another search." : "No students yet. Add the first student using the form."}</td></tr>
                ) : visibleStudents.map((student) => (
                  <tr key={student.id}>
                    <td><div className="student-cell"><span className="avatar">{student.name.trim().charAt(0).toUpperCase()}</span><span><strong>{student.name}</strong><small>{student.email}</small></span></div></td>
                    <td><span className="course-pill">{student.course}</span></td>
                    <td><span className="year-label">Year {student.year}</span></td>
                    <td><div className="row-actions"><button type="button" className="text-action" onClick={() => startEditing(student)}>Edit</button><button type="button" className="text-action text-danger" onClick={() => removeStudent(student)}>Delete</button></div></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="directory-footer"><span>Showing {visibleStudents.length} of {students.length} students</span><span>STUDENT DIRECTORY <b>·</b> 2026</span></div>
        </section>
      </section>
      <footer className="page-footer"><span>CampusDesk <b>·</b> Student Management</span><span>Made for a more organized campus.</span></footer>
    </main>
  );
}