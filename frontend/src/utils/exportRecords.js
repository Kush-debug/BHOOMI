export const exportLocalRecords = () => {
  let records = [];
  try { records = JSON.parse(localStorage.getItem('bhoomi_demo_v1') || '{}').records || []; } catch { records = []; }
  const columns = ['khasra_number', 'khata_number', 'owner_name', 'area', 'area_unit', 'land_classification', 'village', 'tehsil', 'district', 'state', 'year'];
  const quote = (value) => `"${String(value ?? '').replaceAll('"', '""')}"`;
  const csv = [columns.join(','), ...records.map((record) => columns.map((key) => quote(record[key])).join(','))].join('\r\n');
  const url = URL.createObjectURL(new Blob([csv], { type: 'text/csv;charset=utf-8' }));
  const link = document.createElement('a');
  link.href = url;
  link.download = 'bhoomi-demo-registry.csv';
  link.click();
  URL.revokeObjectURL(url);
};
