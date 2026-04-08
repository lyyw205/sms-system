import { useState, useEffect, useCallback } from 'react';
import { toast } from 'sonner';
import { Search, Store } from 'lucide-react';
import dayjs from 'dayjs';

import { Button } from '@/components/ui/button';
import { Select } from '@/components/ui/select';
import { Spinner } from '@/components/ui/spinner';
import { Table, TableHead, TableBody, TableRow, TableHeadCell, TableCell } from '@/components/ui/table';

import { salesReportAPI } from '@/services/api';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface SalesItem {
  date: string;
  category: 'onsite' | 'naver';
  product_name: string;
  amount: number;
  count: number;
}

interface SalesSummary {
  total: number;
  onsite: number;
  naver: number;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function formatAmount(n: number): string {
  return n.toLocaleString('ko-KR');
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function SalesReport() {
  const [dateFrom, setDateFrom] = useState(dayjs().startOf('month').format('YYYY-MM-DD'));
  const [dateTo, setDateTo] = useState(dayjs().format('YYYY-MM-DD'));
  const [groupBy, setGroupBy] = useState<string>('day');

  const [loading, setLoading] = useState(false);
  const [summary, setSummary] = useState<SalesSummary>({ total: 0, onsite: 0, naver: 0 });
  const [items, setItems] = useState<SalesItem[]>([]);

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const params: Record<string, string> = {
        date_from: dateFrom,
        date_to: dateTo,
        group_by: groupBy,
        category: 'onsite', // TODO: 추후 네이버 객실 매출 복구 시 카테고리 필터 UI 추가
      };

      const { data } = await salesReportAPI.get(params as any);
      setSummary(data.summary);
      setItems(data.items);
    } catch {
      toast.error('매출 데이터를 불러오는데 실패했습니다');
    } finally {
      setLoading(false);
    }
  }, [dateFrom, dateTo, groupBy]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="page-title">현장 매출 조회</h1>
          <p className="page-subtitle">파티 입장 체크에서 기록된 현장판매 매출을 조회합니다</p>
        </div>
      </div>

      {/* Filter Bar */}
      <div className="section-card">
        <div className="filter-bar">
          <div className="flex items-center gap-2">
            <label className="text-caption text-[#8B95A1] dark:text-[#8B95A1] whitespace-nowrap">기간</label>
            <input
              type="date"
              value={dateFrom}
              onChange={(e) => setDateFrom(e.target.value)}
              className="rounded-lg border border-[#E5E8EB] dark:border-gray-600 bg-white dark:bg-[#1E1E24] text-body text-[#191F28] dark:text-white px-3 py-1.5"
            />
            <span className="text-[#8B95A1]">~</span>
            <input
              type="date"
              value={dateTo}
              onChange={(e) => setDateTo(e.target.value)}
              className="rounded-lg border border-[#E5E8EB] dark:border-gray-600 bg-white dark:bg-[#1E1E24] text-body text-[#191F28] dark:text-white px-3 py-1.5"
            />
          </div>
          <div className="flex items-center gap-2">
            <label className="text-caption text-[#8B95A1] dark:text-[#8B95A1] whitespace-nowrap">집계</label>
            <Select value={groupBy} onChange={(e) => setGroupBy(e.target.value)} className="px-3 py-1.5">
              <option value="day">일별</option>
              <option value="month">월별</option>
            </Select>
          </div>
          {/* TODO: 추후 네이버 객실 매출 복구 시 카테고리 필터 추가
          <div className="flex items-center gap-2">
            <label className="text-caption text-[#8B95A1] dark:text-[#8B95A1] whitespace-nowrap">카테고리</label>
            <Select value={category} onChange={(e) => setCategory(e.target.value)} className="px-3 py-1.5">
              <option value="">전체</option>
              <option value="onsite">현장판매</option>
              <option value="naver">네이버 객실</option>
            </Select>
          </div>
          */}
          <Button color="blue" size="sm" onClick={fetchData} disabled={loading}>
            {loading ? <Spinner size="sm" className="mr-1.5" /> : <Search className="h-3.5 w-3.5 mr-1.5" />}
            조회
          </Button>
        </div>
      </div>

      {/* TODO: 추후 카테고리 추가 시 요약 카드 복구
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-1 max-w-xs">
        <div className="stat-card">
          <div className="flex items-center gap-3">
            <div className="stat-icon bg-[#FF9F00]/10 text-[#FF9F00] dark:bg-[#FF9F00]/15">
              <Store size={18} />
            </div>
            <div>
              <div className="stat-label">현장판매 합계</div>
              <div className="stat-value">
                {formatAmount(summary.onsite)}
                <span className="ml-0.5 text-label font-normal text-[#B0B8C1]">원</span>
              </div>
            </div>
          </div>
        </div>
        {/* TODO: 추후 네이버 객실 매출 복구 시 총 매출 / 네이버 객실 카드 추가
        <div className="stat-card">
          <div className="flex items-center gap-3">
            <div className="stat-icon bg-[#3182F6]/10 text-[#3182F6] dark:bg-[#3182F6]/15">
              <BarChart3 size={18} />
            </div>
            <div>
              <div className="stat-label">총 매출</div>
              <div className="stat-value">
                {formatAmount(summary.total)}
                <span className="ml-0.5 text-label font-normal text-[#B0B8C1]">원</span>
              </div>
            </div>
          </div>
        </div>
        <div className="stat-card">
          <div className="flex items-center gap-3">
            <div className="stat-icon bg-[#00C9A7]/10 text-[#00C9A7] dark:bg-[#00C9A7]/15">
              <Globe size={18} />
            </div>
            <div>
              <div className="stat-label">네이버 객실</div>
              <div className="stat-value">
                {formatAmount(summary.naver)}
                <span className="ml-0.5 text-label font-normal text-[#B0B8C1]">원</span>
              </div>
            </div>
          </div>
        </div>
      </div>
        */}

      {/* Data Table */}
      <div className="section-card overflow-hidden">
        <div className="overflow-x-auto">
          <Table>
            <TableHead>
              <TableRow>
                <TableHeadCell>날짜</TableHeadCell>
                <TableHeadCell>품명</TableHeadCell>
                <TableHeadCell className="text-right">금액</TableHeadCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {loading ? (
                <TableRow>
                  <TableCell colSpan={3} className="text-center py-12">
                    <Spinner size="md" />
                  </TableCell>
                </TableRow>
              ) : items.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={3} className="text-center py-12 text-[#8B95A1]">
                    조회 결과가 없습니다
                  </TableCell>
                </TableRow>
              ) : (
                <>
                  {items.map((item, i) => (
                    <TableRow key={i}>
                      <TableCell className="tabular-nums">{item.date}</TableCell>
                      <TableCell>{item.product_name}</TableCell>
                      <TableCell className="text-right tabular-nums font-medium">
                        {formatAmount(item.amount)}
                        <span className="ml-0.5 text-[#B0B8C1] font-normal">원</span>
                      </TableCell>
                    </TableRow>
                  ))}
                  {/* 합계 행 */}
                  <TableRow className="bg-[#F8F9FA] dark:bg-[#1E1E24] font-semibold">
                    <TableCell colSpan={2} className="text-right">합계</TableCell>
                    <TableCell className="text-right tabular-nums">
                      {formatAmount(items.reduce((s, i) => s + i.amount, 0))}
                      <span className="ml-0.5 text-[#B0B8C1] font-normal">원</span>
                    </TableCell>
                  </TableRow>
                </>
              )}
            </TableBody>
          </Table>
        </div>
      </div>
    </div>
  );
}
