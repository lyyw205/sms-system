import { useEffect, useState } from 'react'
import {
  Badge,
  Card,
  Progress,
  Spinner,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeadCell,
  TableRow,
} from 'flowbite-react'
import {
  CalendarRange,
  Send,
  Users,
  CheckCircle,
  Clock,
  XCircle,
  Activity,
} from 'lucide-react'
import { dashboardAPI } from '@/services/api'

const STATUS_LABELS: Record<string, string> = {
  pending: '대기중',
  confirmed: '확정',
  cancelled: '취소',
  completed: '완료',
}

function statusBadgeColor(status: string): 'success' | 'warning' | 'failure' | 'info' | 'gray' {
  switch (status) {
    case 'confirmed': return 'success'
    case 'pending':   return 'warning'
    case 'cancelled': return 'failure'
    case 'completed': return 'info'
    default:          return 'gray'
  }
}

function LoadingSkeleton() {
  return (
    <div className="flex items-center justify-center py-32">
      <Spinner size="xl" />
    </div>
  )
}

interface MetricCardProps {
  title: string
  value: string | number
  subtitle?: string
  icon: React.ReactNode
  iconBg: string
}

function MetricCard({ title, value, subtitle, icon, iconBg }: MetricCardProps) {
  return (
    <div className="stat-card">
      <div className="flex items-center justify-between gap-4">
        <div className="min-w-0">
          <p className="stat-label">{title}</p>
          <p className="stat-value mt-1">{value}</p>
          {subtitle && (
            <p className="mt-0.5 text-caption text-gray-400 dark:text-gray-600">{subtitle}</p>
          )}
        </div>
        <div className={`stat-icon ${iconBg}`}>
          {icon}
        </div>
      </div>
    </div>
  )
}

interface GenderBarProps {
  maleCount: number
  femaleCount: number
}

function GenderBar({ maleCount, femaleCount }: GenderBarProps) {
  const total = maleCount + femaleCount
  const malePct = total === 0 ? 50 : Math.round((maleCount / total) * 100)
  const femalePct = 100 - malePct

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-around">
        <div className="text-center">
          <p className="text-caption font-medium text-gray-500">남성</p>
          <p className="mt-1 text-title font-bold text-[#3182F6]">{maleCount}</p>
          <p className="text-caption text-gray-400">{malePct}%</p>
        </div>
        <div className="h-12 w-px bg-[#F2F4F6] dark:bg-gray-800" />
        <div className="text-center">
          <p className="text-caption font-medium text-gray-500">여성</p>
          <p className="mt-1 text-title font-bold text-[#F04452] dark:text-red-400">{femaleCount}</p>
          <p className="text-caption text-gray-400">{femalePct}%</p>
        </div>
      </div>

      <div className="space-y-3">
        <div>
          <div className="mb-1 flex items-center justify-between text-caption">
            <span className="font-medium text-gray-600 dark:text-gray-300">남성</span>
            <span className="text-gray-400">{maleCount}명</span>
          </div>
          <Progress progress={total === 0 ? 0 : malePct} color="blue" size="sm" />
        </div>
        <div>
          <div className="mb-1 flex items-center justify-between text-caption">
            <span className="font-medium text-gray-600 dark:text-gray-300">여성</span>
            <span className="text-gray-400">{femaleCount}명</span>
          </div>
          <Progress progress={total === 0 ? 0 : femalePct} color="pink" size="sm" />
        </div>
      </div>

      <div className="flex items-center justify-center gap-4 text-caption text-gray-400">
        <span className="flex items-center gap-1.5">
          <span className="h-2 w-2 rounded-full bg-[#3182F6]" /> 남성
        </span>
        <span className="flex items-center gap-1.5">
          <span className="h-2 w-2 rounded-full bg-[#F04452]" /> 여성
        </span>
        <span>총 {total}명</span>
      </div>
    </div>
  )
}

interface StatusBreakdownProps {
  pending: number
  confirmed: number
  cancelled: number
  completed: number
}

function StatusBreakdown({ pending, confirmed, cancelled, completed }: StatusBreakdownProps) {
  const total = pending + confirmed + cancelled + completed

  const items = [
    {
      key: 'pending',
      label: '대기중',
      count: pending,
      icon: <Clock size={16} />,
      color: 'text-[#FF9F00] dark:text-amber-400',
      bg: 'bg-[#FFF5E6] dark:bg-[#FF9F00]/10',
    },
    {
      key: 'confirmed',
      label: '확정',
      count: confirmed,
      icon: <CheckCircle size={16} />,
      color: 'text-[#00C9A7] dark:text-emerald-400',
      bg: 'bg-[#E8FAF5] dark:bg-[#00C9A7]/10',
    },
    {
      key: 'cancelled',
      label: '취소',
      count: cancelled,
      icon: <XCircle size={16} />,
      color: 'text-[#F04452] dark:text-red-400',
      bg: 'bg-[#FFEBEE] dark:bg-[#F04452]/10',
    },
    {
      key: 'completed',
      label: '완료',
      count: completed,
      icon: <Activity size={16} />,
      color: 'text-[#3182F6]',
      bg: 'bg-[#E8F3FF] dark:bg-[#3182F6]/10',
    },
  ]

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-2">
        {items.map((item) => (
          <div key={item.key} className={`flex items-center gap-2.5 rounded-xl ${item.bg} p-3`}>
            <span className={item.color}>{item.icon}</span>
            <div>
              <p className="text-heading font-bold text-[#191F28] dark:text-white">{item.count}</p>
              <p className="text-overline font-medium text-gray-500">{item.label}</p>
            </div>
          </div>
        ))}
      </div>

      <div className="space-y-2.5">
        {items.map((item) => {
          const pct = total === 0 ? 0 : Math.round((item.count / total) * 100)
          return (
            <div key={item.key}>
              <div className="mb-1 flex items-center justify-between text-caption">
                <span className="font-medium text-gray-600 dark:text-gray-300">{item.label}</span>
                <span className="text-gray-400">{pct}%</span>
              </div>
              <Progress progress={pct} color="blue" size="sm" />
            </div>
          )
        })}
      </div>

      <div className="pt-2 text-center text-caption text-gray-400">
        전체 <span className="font-semibold text-gray-600 dark:text-gray-300">{total}</span> 건
      </div>
    </div>
  )
}

const Dashboard = () => {
  const [stats, setStats] = useState<any>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    loadStats()
  }, [])

  const loadStats = async () => {
    try {
      const response = await dashboardAPI.getStats()
      setStats(response.data)
    } catch (error) {
      console.error('Failed to load stats:', error)
    } finally {
      setLoading(false)
    }
  }

  if (loading) {
    return <LoadingSkeleton />
  }

  if (!stats) {
    return (
      <div className="empty-state">
        <p className="text-body">데이터를 불러올 수 없습니다.</p>
      </div>
    )
  }

  const campaignSent = stats.campaigns?.total_sent ?? 0
  const maleCount = stats.gender_stats?.male_count ?? 0
  const femaleCount = stats.gender_stats?.female_count ?? 0
  const byStatus = stats.reservations_by_status ?? {}

  return (
    <div className="space-y-6">
      <div>
        <h1 className="page-title">대시보드</h1>
        <p className="page-subtitle">SMS 예약 시스템 현황을 한눈에 확인하세요.</p>
      </div>

      {/* Metric cards */}
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-2">
        <MetricCard
          title="전체 예약"
          value={stats.totals.reservations.toLocaleString()}
          subtitle="누적 예약 건수"
          icon={<CalendarRange size={20} />}
          iconBg="bg-[#E8F3FF] text-[#3182F6] dark:bg-[#3182F6]/15 dark:text-[#3182F6]"
        />
        <MetricCard
          title="캠페인 발송"
          value={campaignSent.toLocaleString()}
          subtitle="누적 발송 건수"
          icon={<Send size={20} />}
          iconBg="bg-[#FFF5E6] text-[#FF9F00] dark:bg-[#FF9F00]/15 dark:text-[#FF9F00]"
        />
      </div>

      {/* Insight cards */}
      <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
        <Card>
          <div className="flex items-center gap-2">
            <Users size={18} className="text-gray-400" />
            <h3 className="text-body font-semibold text-[#191F28] dark:text-white">성별 현황</h3>
          </div>
          <GenderBar maleCount={maleCount} femaleCount={femaleCount} />
        </Card>

        <Card>
          <div className="flex items-center gap-2">
            <CalendarRange size={18} className="text-gray-400" />
            <h3 className="text-body font-semibold text-[#191F28] dark:text-white">예약 상태</h3>
          </div>
          <StatusBreakdown
            pending={byStatus.pending ?? 0}
            confirmed={byStatus.confirmed ?? 0}
            cancelled={byStatus.cancelled ?? 0}
            completed={byStatus.completed ?? 0}
          />
        </Card>
      </div>

      {/* Recent reservations */}
      <div className="section-card">
        <div className="section-header">
          <div className="flex items-center gap-2">
            <CalendarRange size={18} className="text-gray-400" />
            <h3 className="text-body font-semibold text-[#191F28] dark:text-white">최근 예약</h3>
          </div>
        </div>
        <div className="overflow-x-auto">
          <Table hoverable striped>
            <TableHead>
              <TableRow>
                <TableHeadCell>고객명</TableHeadCell>
                <TableHeadCell>전화번호</TableHeadCell>
                <TableHeadCell>일시</TableHeadCell>
                <TableHeadCell>상태</TableHeadCell>
              </TableRow>
            </TableHead>
            <TableBody className="divide-y">
              {(stats.recent_reservations ?? []).length === 0 ? (
                <TableRow>
                  <TableCell colSpan={4}>
                    <div className="py-4 text-center text-label text-gray-400">
                      예약 내역이 없습니다
                    </div>
                  </TableCell>
                </TableRow>
              ) : (
                (stats.recent_reservations ?? []).slice(0, 5).map((r: any, idx: number) => (
                  <TableRow key={r.id ?? idx}>
                    <TableCell>
                      <span className="font-medium text-gray-900 dark:text-white">{r.customer_name ?? '—'}</span>
                    </TableCell>
                    <TableCell>
                      <span className="tabular-nums text-gray-500">{r.phone ?? '—'}</span>
                    </TableCell>
                    <TableCell>
                      <span className="text-gray-500">{r.check_in_date ?? ''} {r.check_in_time ?? ''}</span>
                    </TableCell>
                    <TableCell>
                      <Badge color={statusBadgeColor(r.status)} size="sm">
                        {STATUS_LABELS[r.status] ?? r.status}
                      </Badge>
                    </TableCell>
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>
        </div>
      </div>
    </div>
  )
}

export default Dashboard
