import React, { useState, useEffect } from 'react';

// Defines the base record we get from backend, but allows dynamic keys for user-added columns
export interface HouseholdRecord {
    id: number;
    unit: string;
    unit_clean: string;
    floor: string;
    name: string;
    car_parking: string;
    scooter_parking: string;
    bike_parking: string;
    base_fee: number;
    car_cleaning_fee: number;
    scooter_cleaning_fee: number;
    bike_cleaning_fee: number;
    temp_rent: number;
    previous_arrears: number;
    expected: number;
    paid: number;
    status: 'Paid' | 'Unpaid' | 'Underpaid' | 'Overpaid';
    [key: string]: any; // Allow dynamic columns
}

interface Props {
    data: HouseholdRecord[];
    onDataChange?: (newData: HouseholdRecord[]) => void;
    onSaveRow?: (record: HouseholdRecord) => Promise<void>;
}

const MONEY_COLUMNS = ['base_fee', 'car_cleaning_fee', 'scooter_cleaning_fee', 'bike_cleaning_fee', 'temp_rent', 'previous_arrears', 'expected', 'paid', 'prepaid_overpaid'];

const COLUMN_LABELS: Record<string, string> = {
    unit: '戶別',
    floor: '樓層',
    name: '姓名',
    car_parking: '汽車車位',
    scooter_parking: '機車車位',
    bike_parking: '腳踏車位',
    base_fee: '管理費',
    car_cleaning_fee: '汽車清潔費',
    scooter_cleaning_fee: '機車清潔費',
    bike_cleaning_fee: '腳踏車清潔費',
    temp_rent: '臨時租金',
    previous_arrears: '前期欠款',
    expected: '應繳金額',
    paid: '已繳金額',
    prepaid_overpaid: '預繳溢繳',
    status: '狀態',
};

export const EditableDataGrid: React.FC<Props> = ({ data, onDataChange, onSaveRow }) => {
    const [records, setRecords] = useState<HouseholdRecord[]>(data);
    const [savingRows, setSavingRows] = useState<Record<number, boolean>>({});
    const [savedRows, setSavedRows] = useState<Record<number, boolean>>({});
    const [focusedCell, setFocusedCell] = useState<string | null>(null);
    const [columns, setColumns] = useState<string[]>([
        'unit', 'floor', 'name',
        'car_parking', 'scooter_parking', 'bike_parking',
        'base_fee', 'car_cleaning_fee', 'scooter_cleaning_fee', 'bike_cleaning_fee', 'temp_rent',
        'previous_arrears', 'expected', 'paid', 'prepaid_overpaid', 'status'
    ]);

    // When props data changes (e.g. new file uploaded), update state
    useEffect(() => {
        setRecords(data);
    }, [data]);

    const handleCellChange = (rowIndex: number, columnKey: string, value: string) => {
        // Strip commas from money columns so we store the raw number
        const cleanValue = MONEY_COLUMNS.includes(columnKey) ? value.replace(/,/g, '') : value;
        const updatedRecords = [...records];
        updatedRecords[rowIndex] = {
            ...updatedRecords[rowIndex],
            [columnKey]: cleanValue
        };
        setRecords(updatedRecords);
        if (onDataChange) {
            onDataChange(updatedRecords);
        }
    };

    const handleCellBlur = async (rowIndex: number, columnKey: string, newValue: string) => {
        setFocusedCell(null);
        // Strip commas for comparison
        const cleanValue = MONEY_COLUMNS.includes(columnKey) ? newValue.replace(/,/g, '') : newValue;
        // If the value hasn't changed compared to the original prop data, do nothing
        if (data[rowIndex][columnKey] == cleanValue) return;

        if (onSaveRow) {
            setSavingRows(prev => ({ ...prev, [rowIndex]: true }));
            try {
                await onSaveRow(records[rowIndex]);
                setSavedRows(prev => ({ ...prev, [rowIndex]: true }));
                setTimeout(() => {
                    setSavedRows(prev => ({ ...prev, [rowIndex]: false }));
                }, 2000);
            } catch (err) {
                console.error("Failed to save row", err);
                alert("Failed to save changes.");
            } finally {
                setSavingRows(prev => ({ ...prev, [rowIndex]: false }));
            }
        }
    };

    const handleAddColumn = () => {
        const newColName = prompt("Enter new column name:");
        if (newColName && !columns.includes(newColName)) {
            setColumns([...columns, newColName]);
        }
    };

    // Helper to format specific known columns
    const renderCellContent = (key: string, val: any) => {
        if (val === undefined || val === null || val === '') return '-';
        // Format known money columns
        if (MONEY_COLUMNS.includes(key)) {
            const noPrefix = ['previous_arrears', 'expected', 'prepaid_overpaid'];
            if (noPrefix.includes(key)) {
                return Number(val).toLocaleString();
            }
            return `NT$ ${Number(val).toLocaleString()}`;
        }
        return String(val);
    };

    // Format editable money cell: show raw number when focused, formatted when not
    const formatEditableValue = (rowIndex: number, colKey: string, val: any) => {
        if (val === undefined || val === null || val === '') return '';
        const cellId = `${rowIndex}-${colKey}`;
        if (MONEY_COLUMNS.includes(colKey) && focusedCell !== cellId) {
            return Number(val).toLocaleString();
        }
        return val;
    };

    return (
        <div className="editable-grid-container">
            <div className="grid-header-actions">
                <h2 style={{ color: 'var(--text-primary)' }}>住戶主檔資料</h2>
                <button className="btn btn-secondary" onClick={handleAddColumn}>
                    + 新增自訂欄位
                </button>
            </div>

            <div className="table-responsive">
                <table className="editable-table">
                    <thead>
                        <tr>
                            {columns.map((col, idx) => {
                                const colClass = col === 'floor' ? 'col-narrow'
                                    : col === 'unit' ? 'col-unit'
                                        : ['scooter_parking', 'bike_parking'].includes(col) ? 'col-compact'
                                            : ['base_fee', 'car_cleaning_fee', 'scooter_cleaning_fee', 'bike_cleaning_fee', 'temp_rent', 'paid'].includes(col) ? 'col-money'
                                                : '';
                                return (
                                    <th key={idx} className={colClass}>
                                        {COLUMN_LABELS[col] || col.replace(/_/g, ' ').toUpperCase()}
                                    </th>
                                );
                            })}
                        </tr>
                    </thead>
                    <tbody>
                        {records.map((row, rowIndex) => (
                            <tr key={rowIndex}>
                                {columns.map((colKey, colIndex) => {
                                    const isReadOnly = ['status', 'expected', 'previous_arrears', 'prepaid_overpaid'].includes(colKey);
                                    // Compute prepaid_overpaid on-the-fly (only show when Overpaid)
                                    const cellValue = colKey === 'prepaid_overpaid'
                                        ? (row.status === 'Overpaid'
                                            ? (Number(row.paid) || 0) - ((Number(row.expected) || 0) + (Number(row.previous_arrears) || 0))
                                            : '')
                                        : row[colKey];
                                    let cellClass = '';
                                    if (colKey === 'status') {
                                        cellClass = row.status === 'Paid' ? 'status-paid' : 'status-unpaid';
                                    }
                                    const colClass = colKey === 'floor' ? 'col-narrow'
                                        : colKey === 'unit' ? 'col-unit'
                                            : ['scooter_parking', 'bike_parking'].includes(colKey) ? 'col-compact'
                                                : ['base_fee', 'car_cleaning_fee', 'scooter_cleaning_fee', 'bike_cleaning_fee', 'temp_rent', 'paid'].includes(colKey) ? 'col-money'
                                                    : '';

                                    return (
                                        <td key={colIndex} className={`${cellClass} ${colClass}`}>
                                            {isReadOnly ? (
                                                <span className={`readonly-cell ${cellClass}`}>
                                                    {colKey === 'status' ? (
                                                        <span className={`tag ${row.status === 'Paid' ? 'interest' :
                                                            row.status === 'Overpaid' ? 'overpaid' : 'telecom'
                                                            }`}>{row.status}</span>
                                                    ) : (
                                                        renderCellContent(colKey, cellValue)
                                                    )}
                                                </span>
                                            ) : (
                                                <input
                                                    type="text"
                                                    value={row[colKey] !== undefined ? formatEditableValue(rowIndex, colKey, row[colKey]) : ''}
                                                    onChange={(e) => handleCellChange(rowIndex, colKey, e.target.value)}
                                                    onFocus={() => setFocusedCell(`${rowIndex}-${colKey}`)}
                                                    onBlur={(e) => handleCellBlur(rowIndex, colKey, e.target.value)}
                                                    onKeyDown={(e) => {
                                                        if (e.key === 'Enter') {
                                                            e.currentTarget.blur();
                                                        }
                                                    }}
                                                    className={`editable-input ${savingRows[rowIndex] ? 'saving-active' : ''} ${savedRows[rowIndex] ? 'saved-success' : ''}`}
                                                    placeholder="-"
                                                />
                                            )}
                                        </td>
                                    );
                                })}
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>
        </div>
    );
};
