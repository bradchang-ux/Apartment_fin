import { useState, useMemo, useEffect } from 'react'
import './App.css'
import { EditableDataGrid, type HouseholdRecord } from './components/EditableDataGrid'

const API_BASE = import.meta.env.DEV ? 'http://localhost:8000' : '';

interface Transaction {
  date: string;
  category: string;
  code: string;
  income: string;
  expense: string;
  balance: string;
  remarks: string;
  virtualAccount: string;
}

interface OrphanRecord {
  code: string;
  amount: number;
}

interface ReconciliationResult {
  paid: HouseholdRecord[];
  unpaid: HouseholdRecord[];
  orphaned: OrphanRecord[];
}

function App() {
  const [transactions, setTransactions] = useState<Transaction[]>([]);
  const [reconciliation, setReconciliation] = useState<ReconciliationResult | null>(null);
  const [initialData, setInitialData] = useState<HouseholdRecord[]>([]);
  const [viewMode, setViewMode] = useState<'master' | 'transactions' | 'reconciliation'>('master');
  const [selectedMonth, setSelectedMonth] = useState<string>('');
  const [availableMonths, setAvailableMonths] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showUploader, setShowUploader] = useState(false);
  const [showResetConfirm, setShowResetConfirm] = useState(false);

  const [bankFile, setBankFile] = useState<File | null>(null);
  const [virtualFile, setVirtualFile] = useState<File | null>(null);

  // Load household data (depends on selectedMonth)
  useEffect(() => {
    let url = `${API_BASE}/api/households`;
    if (selectedMonth) {
      url += `?month=${selectedMonth}`;
    }
    fetch(url)
      .then(res => res.json())
      .then(result => {
        if (result.data) {
          setInitialData(result.data);
          // Rebuild reconciliation split from the loaded data
          const paidArr = result.data.filter((r: HouseholdRecord) => r.status === 'Paid' || r.status === 'Overpaid');
          const unpaidArr = result.data.filter((r: HouseholdRecord) => r.status !== 'Paid' && r.status !== 'Overpaid');
          // Only show reconciliation if there are any paid/underpaid (i.e. some reconciliation happened)
          const hasReconciliation = result.data.some((r: HouseholdRecord) => r.paid > 0);
          if (hasReconciliation) {
            setReconciliation(prev => ({
              paid: paidArr,
              unpaid: unpaidArr,
              orphaned: prev?.orphaned || []
            }));
          } else {
            setReconciliation(null);
          }
        }
        if (result.meta) {
          setAvailableMonths(result.meta.available_months || []);
          setSelectedMonth(result.meta.selected_month || '');
        }
      })
      .catch(err => console.error("Failed to load households", err));

    // Also load transactions for this month
    if (selectedMonth) {
      fetch(`${API_BASE}/api/transactions?month=${selectedMonth}`)
        .then(res => res.json())
        .then(result => {
          if (result.data) {
            setTransactions(result.data);
          }
        })
        .catch(err => console.error("Failed to load transactions", err));
    }
  }, [selectedMonth]);

  const handleUpload = async () => {
    if (!bankFile) {
      setError("Please select at least the Bank tx file.");
      return;
    }

    setLoading(true);
    setError(null);

    const formData = new FormData();
    formData.append('bank_file', bankFile);
    formData.append('billing_month', selectedMonth);

    if (virtualFile) {
      formData.append('virtual_file', virtualFile);
    }

    try {
      const response = await fetch(`${API_BASE}/api/upload`, {
        method: 'POST',
        body: formData,
      });

      if (!response.ok) {
        throw new Error('Upload failed');
      }

      const result = await response.json();

      if (result.data.reconciliation !== undefined) {
        setTransactions(result.data.transactions);
        setReconciliation(result.data.reconciliation);
        setViewMode('reconciliation'); // Switch to reconciliation view upon success
        setShowUploader(false);
      } else {
        setTransactions(result.data);
        setReconciliation(null);
        setViewMode('transactions');
        setShowUploader(false);
      }
    } catch (err: any) {
      setError(err.message || 'An error occurred during file upload.');
    } finally {
      setLoading(false);
    }
  };

  const handleSaveRow = async (record: HouseholdRecord) => {
    const res = await fetch(`${API_BASE}/api/households/${record.id}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        name: record.name,
        car_parking: record.car_parking,
        scooter_parking: record.scooter_parking,
        bike_parking: record.bike_parking,
        base_fee: Number(record.base_fee) || 0,
        car_cleaning_fee: Number(record.car_cleaning_fee) || 0,
        scooter_cleaning_fee: Number(record.scooter_cleaning_fee) || 0,
        bike_cleaning_fee: Number(record.bike_cleaning_fee) || 0,
        temp_rent: Number(record.temp_rent) || 0,
        expected: Number(record.expected) || 0,
        paid: Number(record.paid) || 0,
      })
    });

    if (!res.ok) {
      throw new Error("Failed to save record");
    }

    // Optimistically update local state so views don't revert
    setInitialData(prev => prev.map(row => row.id === record.id ? record : row));
    if (reconciliation) {
      setReconciliation(prev => {
        if (!prev) return prev;
        return {
          ...prev,
          paid: prev.paid.map(r => r.id === record.id ? record : r),
          unpaid: prev.unpaid.map(r => r.id === record.id ? record : r),
        }
      });
    }

    // Trigger silent refresh from backend so frontend exactly mimics DB calculated status / arrears
    let url = `${API_BASE}/api/households`;
    if (selectedMonth) {
      url += `?month=${selectedMonth}`;
    }
    try {
      const refreshRes = await fetch(url);
      const result = await refreshRes.json();
      if (result.data) {
        setInitialData(result.data);
        if (reconciliation) {
          // Update just the relevant split for reconciliation view
          const paidArr = result.data.filter((r: HouseholdRecord) => r.status === 'Paid' || r.status === 'Overpaid');
          const unpaidArr = result.data.filter((r: HouseholdRecord) => r.status !== 'Paid' && r.status !== 'Overpaid');
          setReconciliation(prev => {
            if (!prev) return prev;
            return {
              ...prev,
              paid: paidArr,
              unpaid: unpaidArr
            };
          });
        }
      }
    } catch (err) {
      console.error("Failed silent data refresh", err);
    }
  };

  const executeResetDb = async () => {
    setLoading(true);
    setShowResetConfirm(false);
    try {
      const response = await fetch(`${API_BASE}/api/reset_db`, { method: 'POST' });
      if (!response.ok) throw new Error("Failed to reset database");

      // Reload page to start fresh
      window.location.reload();
    } catch (err) {
      alert("Reset failed: " + err);
      setLoading(false);
    }
  };

  const handleResetDb = () => {
    setShowResetConfirm(true);
  };

  // Combine Paid/Unpaid for the master grid, fallback to initialData if no reconciliation yet
  const masterData = useMemo(() => {
    if (reconciliation) {
      return [...reconciliation.paid, ...reconciliation.unpaid].sort((a, b) => a.order - b.order);
    }
    return initialData.sort((a, b) => a.order - b.order);
  }, [reconciliation, initialData]);

  // Billing cycle summary calculations
  const billingSummary = useMemo(() => {
    const data = masterData;
    let arrearsCollected = 0;  // 前期欠繳已收
    let overpaidTotal = 0;     // 預溢繳
    let totalPaid = 0;         // 實際入帳總計
    let totalDue = 0;          // 應繳總額 (expected + previous_arrears)

    for (const r of data) {
      const paid = Number(r.paid) || 0;
      const expected = Number(r.expected) || 0;
      const arrears = Number(r.previous_arrears) || 0;
      const due = expected + arrears;

      totalPaid += paid;
      totalDue += due;

      // 前期欠繳已收: for units with arrears > 0, how much of their payment went to clearing arrears
      if (arrears > 0 && paid > 0) {
        arrearsCollected += Math.min(paid, arrears);
      }

      // 預溢繳: for units that overpaid, the excess amount
      if (paid > due && due >= 0) {
        overpaidTotal += (paid - due);
      }
    }

    const outstanding = totalPaid - totalDue; // 未繳款 (negative = still owed)

    return { arrearsCollected, overpaidTotal, totalPaid, outstanding };
  }, [masterData]);

  return (
    <div className={`app-container fluid`}>
      <header>
        <div className="brand">公寓財務管理</div>
        <div className="view-toggles" style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
          {availableMonths.length > 0 && (
            <select
              className="btn btn-secondary"
              value={selectedMonth}
              onChange={(e) => setSelectedMonth(e.target.value)}
              style={{ padding: '0.4rem 1rem', fontSize: '0.9rem', cursor: 'pointer' }}
            >
              {availableMonths.map(m => (
                <option key={m} value={m}>{m} Billing Cycle</option>
              ))}
            </select>
          )}
          {!showUploader && viewMode === 'master' && (
            <>
              <button
                className="btn"
                onClick={() => setShowUploader(true)}
                style={{ background: '#34d399', color: '#064e3b' }}
              >
                💸 對帳作業
              </button>
              <button
                className="btn btn-secondary"
                onClick={handleResetDb}
                style={{ color: '#f87171', borderColor: 'rgba(248, 113, 113, 0.3)' }}
              >
                ⚠️ 清除資料庫
              </button>
            </>
          )}

          {/* Navigation Tabs */}
          <div style={{ marginLeft: 'auto', display: 'flex', gap: '0.5rem' }}>
            <button
              className={`btn ${viewMode === 'master' ? 'active' : 'btn-secondary'}`}
              onClick={() => { setViewMode('master'); setShowUploader(false); }}
            >
              主檔資料
            </button>
            {transactions.length > 0 && (
              <button
                className={`btn ${viewMode === 'transactions' ? 'active' : 'btn-secondary'}`}
                onClick={() => setViewMode('transactions')}
              >
                銀行交易紀錄
              </button>
            )}
            {reconciliation && (
              <button
                className={`btn ${viewMode === 'reconciliation' ? 'active' : 'btn-secondary'}`}
                onClick={() => setViewMode('reconciliation')}
                style={viewMode !== 'reconciliation' ? { color: '#34d399', borderColor: 'rgba(52, 211, 153, 0.3)' } : {}}
              >
                對帳報告
              </button>
            )}
          </div>
        </div>
      </header>

      {/* Uploader Section */}
      {showUploader && (
        <section className="glass-panel uploader-container" style={{ border: '1px solid #34d399', animation: 'fadeIn 0.3s ease' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
            <h3 style={{ margin: 0, color: 'var(--text-primary)' }}>匯入銀行交易</h3>
            <button className="btn btn-secondary" onClick={() => setShowUploader(false)}>取消</button>
          </div>
          <p>拖曳或選擇您的銀行對帳單和虛擬帳號對照表來進行分析與對帳。</p>
          <div className="file-inputs">
            <div className="file-input-wrapper">
              <label>銀行匯出檔（.docx, .xls）</label>
              <input
                type="file"
                accept=".docx,.xls,.csv"
                onChange={(e) => setBankFile(e.target.files?.[0] || null)}
              />
            </div>
            <div className="file-input-wrapper">
              <label>虛擬帳號對照表 (.xls)</label>
              <input
                type="file"
                accept=".xls,.xlsx"
                onChange={(e) => setVirtualFile(e.target.files?.[0] || null)}
              />
            </div>
          </div>

          <button
            className="btn"
            onClick={handleUpload}
            disabled={loading || !bankFile}
            style={{ width: '100%', marginTop: '1rem' }}
          >
            {loading ? '比對引擎處理中...' : '執行對帳'}
          </button>
          {error && <div style={{ color: 'var(--danger)', marginTop: '1rem' }}>{error}</div>}
        </section>
      )}

      {/* Reset Confirmation Modal */}
      {showResetConfirm && (
        <section className="glass-panel" style={{
          border: '1px solid #f87171',
          animation: 'fadeIn 0.3s ease',
          display: 'flex', flexDirection: 'column', gap: '1rem', alignItems: 'center', textAlign: 'center',
          padding: '2.5rem'
        }}>
          <h3 style={{ margin: 0, color: '#f87171', fontSize: '1.5rem' }}>⚠️ 確定要清除資料庫？</h3>
          <p style={{ color: 'var(--text-secondary)', fontSize: '1.1rem', maxWidth: '500px' }}>
            確定要清除整個資料庫並還原到初始狀態嗎？所有手動輸入的資料、已對帳的付款紀錄和歷史紀錄都將遺失。<strong>此操作無法復原。</strong>
          </p>
          <div style={{ display: 'flex', gap: '1rem', marginTop: '1rem' }}>
            <button className="btn btn-secondary" onClick={() => setShowResetConfirm(false)}>
              取消
            </button>
            <button className="btn" style={{ background: '#f87171', color: '#450a0a' }} onClick={executeResetDb}>
              {loading ? '清除中...' : '是的，清除所有資料'}
            </button>
          </div>
        </section>
      )}

      {/* Master Data Grid View */}
      {!showUploader && viewMode === 'master' && (
        <>
          {/* Billing Cycle Summary */}
          <section className="dashboard-grid" style={{ gridTemplateColumns: 'repeat(4, 1fr)' }}>
            <div className="glass-panel stat-card">
              <span className="stat-label">前期欠繳已收</span>
              <span className="stat-value" style={{ fontSize: '1.6rem' }}>NT$ {billingSummary.arrearsCollected.toLocaleString()}</span>
            </div>
            <div className="glass-panel stat-card">
              <span className="stat-label">預溢繳</span>
              <span className="stat-value" style={{ fontSize: '1.6rem', color: '#a78bfa' }}>NT$ {billingSummary.overpaidTotal.toLocaleString()}</span>
            </div>
            <div className="glass-panel stat-card income">
              <span className="stat-label">實際入帳總計</span>
              <span className="stat-value income" style={{ fontSize: '1.6rem' }}>NT$ {billingSummary.totalPaid.toLocaleString()}</span>
            </div>
            <div className={`glass-panel stat-card ${billingSummary.outstanding < 0 ? 'expense' : 'balance'}`}>
              <span className="stat-label">未繳款</span>
              <span className={`stat-value ${billingSummary.outstanding < 0 ? 'expense' : ''}`} style={{ fontSize: '1.6rem' }}>
                NT$ {billingSummary.outstanding.toLocaleString()}
              </span>
            </div>
          </section>

          <section className="glass-panel" style={{ padding: 0, overflow: 'hidden' }}>
            <EditableDataGrid data={masterData} onSaveRow={handleSaveRow} />
          </section>
        </>
      )}

      {/* Data Table */}
      {viewMode === 'transactions' && transactions.length > 0 && (
        <section className="glass-panel table-container">
          <h2 style={{ padding: '1.5rem 1.5rem 0', color: 'var(--text-primary)' }}>銀行交易紀錄</h2>
          <table>
            <thead>
              <tr>
                <th>日期</th>
                <th>類別</th>
                <th>代碼</th>
                <th>收入</th>
                <th>支出</th>
                <th>餘額</th>
                <th>備註</th>
                <th>虛擬帳號</th>
              </tr>
            </thead>
            <tbody>
              {transactions.map((tx, idx) => {
                let tagClass = '';
                if (tx.category === '利息收入') tagClass = 'interest';
                else if (tx.category === '電信費') tagClass = 'telecom';
                else if (tx.category === '台電') tagClass = 'power';

                return (
                  <tr key={idx}>
                    <td>{tx.date}</td>
                    <td>
                      {tx.category && <span className={`tag ${tagClass}`}>{tx.category}</span>}
                    </td>
                    <td>{tx.code}</td>
                    <td className="val-income">{tx.income ? `+${tx.income}` : ''}</td>
                    <td className="val-expense">{tx.expense ? `-${tx.expense}` : ''}</td>
                    <td className="val-balance">{tx.balance}</td>
                    <td style={{ opacity: 0.8 }}>{tx.remarks}</td>
                    <td style={{ fontFamily: 'monospace', opacity: 0.8 }}>{tx.virtualAccount}</td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </section>
      )}

      {/* Reconciliation Tables */}
      {viewMode === 'reconciliation' && reconciliation && (
        <div className="reconciliation-grid">
          {/* Unpaid Households */}
          <section className="glass-panel table-container">
            <h2 style={{ padding: '1.5rem 1.5rem 0', color: 'var(--danger)' }}>未繳 / 欠繳住戶 ({reconciliation.unpaid.length})</h2>
            <table>
              <thead>
                <tr>
                  <th>戶別</th>
                  <th>姓名</th>
                  <th>應繳金額</th>
                  <th>實繳金額</th>
                  <th>狀態</th>
                </tr>
              </thead>
              <tbody>
                {reconciliation.unpaid.map((record, idx) => (
                  <tr key={idx}>
                    <td style={{ fontWeight: 'bold' }}>{record.unit}</td>
                    <td>{record.full_name}</td>
                    <td>NT$ {record.expected.toLocaleString()}</td>
                    <td>NT$ {record.paid.toLocaleString()}</td>
                    <td><span className="tag telecom">{record.status}</span></td>
                  </tr>
                ))}
                {reconciliation.unpaid.length === 0 && (
                  <tr><td colSpan={5} style={{ textAlign: 'center', opacity: 0.5 }}>所有住戶都已繳費！</td></tr>
                )}
              </tbody>
            </table>
          </section>

          {/* Paid Households */}
          <section className="glass-panel table-container">
            <h2 style={{ padding: '1.5rem 1.5rem 0', color: 'var(--success)' }}>已繳住戶 ({reconciliation.paid.length})</h2>
            <table>
              <thead>
                <tr>
                  <th>戶別</th>
                  <th>姓名</th>
                  <th>應繳金額</th>
                  <th>實繳金額</th>
                  <th>狀態</th>
                </tr>
              </thead>
              <tbody>
                {reconciliation.paid.map((record, idx) => (
                  <tr key={idx}>
                    <td style={{ fontWeight: 'bold' }}>{record.unit}</td>
                    <td>{record.full_name}</td>
                    <td>NT$ {record.expected.toLocaleString()}</td>
                    <td>NT$ {record.paid.toLocaleString()}</td>
                    <td><span className={`tag ${record.status === 'Overpaid' ? 'overpaid' : 'interest'}`}>{record.status}</span></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </section>
        </div>
      )}
    </div>
  )
}

export default App
