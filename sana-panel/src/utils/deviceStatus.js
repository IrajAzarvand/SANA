export const managementStatusMap = {
  warehouse: { label: 'در انبار', variant: 'info' },
  installed: { label: 'نصب شده', variant: 'info' },
  active: { label: 'فعال', variant: 'success' },
  ready: { label: 'آماده تعیین تکلیف', variant: 'warning' },
  in_repair: { label: 'در حال تعمیر', variant: 'warning' },
  faulty: { label: 'خراب', variant: 'danger' },
  lost: { label: 'گمشده', variant: 'warning' },
  stolen: { label: 'سرقت شده', variant: 'danger' },
  disconnected: { label: 'قطع سرویس', variant: 'neutral' },
  unusable: { label: 'غیرقابل استفاده', variant: 'danger' },
  disposed: { label: 'امحاء شده', variant: 'danger' },

  // Compatibility for historical operation records created before status normalization.
  sold: { label: 'نصب شده', variant: 'info' },
  retired: { label: 'غیرقابل استفاده', variant: 'danger' },
};

export const getManagementStatus = (status) => (
  managementStatusMap[status] || managementStatusMap.warehouse
);
