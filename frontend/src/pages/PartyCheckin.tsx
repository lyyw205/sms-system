import { useState, useEffect, useCallback } from 'react'
import { Button, Badge, Modal, ModalHeader, ModalBody, Spinner } from 'flowbite-react'
import { Users, CheckCircle, AlertTriangle } from 'lucide-react'
import { partyCheckinAPI } from '@/services/api'
import { toast } from 'sonner'

interface PartyGuest {
  id: number
  customer_name: string
  phone: string
  gender: string | null
  male_count: number | null
  female_count: number | null
  checked_in: boolean
  checked_in_at: string | null
}

function getTodayStr(): string {
  const d = new Date()
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${y}-${m}-${day}`
}

function formatTime(isoStr: string | null): string {
  if (!isoStr) return '-'
  const d = new Date(isoStr)
  const h = String(d.getHours()).padStart(2, '0')
  const min = String(d.getMinutes()).padStart(2, '0')
  return `${h}:${min}`
}

export default function PartyCheckin() {
  const [selectedDate, setSelectedDate] = useState(getTodayStr())
  const [guests, setGuests] = useState<PartyGuest[]>([])
  const [loading, setLoading] = useState(false)
  const [toggling, setToggling] = useState<number | null>(null)

  // 취소 확인 모달
  const [cancelModal, setCancelModal] = useState<{ open: boolean; guest: PartyGuest | null }>({
    open: false,
    guest: null,
  })

  const fetchGuests = useCallback(async (date: string) => {
    setLoading(true)
    try {
      const res = await partyCheckinAPI.getList(date)
      setGuests(res.data)
    } catch {
      toast.error('파티 예약자 목록을 불러오지 못했습니다')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchGuests(selectedDate)
  }, [selectedDate, fetchGuests])

  const handleRowClick = (guest: PartyGuest) => {
    if (guest.checked_in) {
      // 입장 완료 → 취소 확인 모달
      setCancelModal({ open: true, guest })
    } else {
      // 미입장 → 바로 체크인
      doToggle(guest)
    }
  }

  const doToggle = async (guest: PartyGuest) => {
    setToggling(guest.id)
    try {
      const res = await partyCheckinAPI.toggle(guest.id, selectedDate)
      const { checked_in, checked_in_at } = res.data
      setGuests((prev) =>
        prev.map((g) =>
          g.id === guest.id ? { ...g, checked_in, checked_in_at } : g
        )
      )
      if (checked_in) {
        toast.success(`${guest.customer_name}님 입장 완료`)
      } else {
        toast.success(`${guest.customer_name}님 입장 취소`)
      }
    } catch {
      toast.error('처리 중 오류가 발생했습니다')
    } finally {
      setToggling(null)
    }
  }

  const handleCancelConfirm = async () => {
    if (!cancelModal.guest) return
    setCancelModal({ open: false, guest: null })
    await doToggle(cancelModal.guest)
  }

  const checkedInCount = guests.filter((g) => g.checked_in).length
  const totalCount = guests.length

  return (
    <div className="space-y-6">
      {/* 헤더 */}
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="page-title">파티 입장 체크</h1>
          <p className="page-subtitle">파티 참여 예약자의 입장을 체크합니다</p>
        </div>
        <div className="flex items-center gap-2">
          <input
            type="date"
            value={selectedDate}
            onChange={(e) => setSelectedDate(e.target.value)}
            className="rounded-lg border border-[#E5E8EB] bg-white px-3 py-2 text-body text-[#191F28] focus:border-[#3182F6] focus:outline-none dark:border-gray-600 dark:bg-[#1E1E24] dark:text-white"
          />
        </div>
      </div>

      {/* 카운터 stat-card */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
        <div className="stat-card flex items-center gap-3">
          <div className="stat-icon flex items-center justify-center bg-[#E8F3FF] dark:bg-[#3182F6]/15">
            <Users size={18} className="text-[#3182F6]" />
          </div>
          <div>
            <div className="stat-label">전체 예약자</div>
            <div className="stat-value tabular-nums">
              {totalCount}
              <span className="ml-0.5 text-label font-normal text-[#B0B8C1]">명</span>
            </div>
          </div>
        </div>

        <div className="stat-card flex items-center gap-3">
          <div className="stat-icon flex items-center justify-center bg-[#E6FAF5] dark:bg-[#00C9A7]/15">
            <CheckCircle size={18} className="text-[#00C9A7]" />
          </div>
          <div>
            <div className="stat-label">입장 완료</div>
            <div className="stat-value tabular-nums">
              {checkedInCount}
              <span className="ml-0.5 text-label font-normal text-[#B0B8C1]">명</span>
            </div>
          </div>
        </div>

        <div className="stat-card flex items-center gap-3 col-span-2 sm:col-span-1">
          <div className="stat-icon flex items-center justify-center bg-[#FFF4E5] dark:bg-[#FF9F00]/15">
            <AlertTriangle size={18} className="text-[#FF9F00]" />
          </div>
          <div>
            <div className="stat-label">미입장</div>
            <div className="stat-value tabular-nums">
              {totalCount - checkedInCount}
              <span className="ml-0.5 text-label font-normal text-[#B0B8C1]">명</span>
            </div>
          </div>
        </div>
      </div>

      {/* 테이블 */}
      <div className="section-card overflow-hidden">
        <div className="section-header">
          <span className="text-heading font-semibold text-[#191F28] dark:text-white">
            파티 예약자 목록
          </span>
          <span className="text-label text-[#8B95A1]">
            {checkedInCount}/{totalCount}명 입장 완료
          </span>
        </div>

        {loading ? (
          <div className="flex items-center justify-center py-16">
            <Spinner size="lg" />
          </div>
        ) : guests.length === 0 ? (
          <div className="empty-state">
            <Users size={40} className="text-[#B0B8C1]" />
            <p className="mt-3 text-body text-[#8B95A1]">해당 날짜의 파티 예약자가 없습니다</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b border-[#E5E8EB] bg-[#F8F9FA] dark:border-gray-800 dark:bg-[#1E1E24]">
                  <th className="px-4 py-3 text-left text-caption font-semibold uppercase tracking-wide text-[#8B95A1]">
                    이름
                  </th>
                  <th className="px-4 py-3 text-center text-caption font-semibold uppercase tracking-wide text-[#8B95A1]">
                    성별
                  </th>
                  <th className="px-4 py-3 text-center text-caption font-semibold uppercase tracking-wide text-[#8B95A1]">
                    인원
                  </th>
                  <th className="px-4 py-3 text-center text-caption font-semibold uppercase tracking-wide text-[#8B95A1]">
                    입장 시간
                  </th>
                  <th className="px-4 py-3 text-center text-caption font-semibold uppercase tracking-wide text-[#8B95A1]">
                    상태
                  </th>
                </tr>
              </thead>
              <tbody>
                {guests.map((guest) => (
                  <tr
                    key={guest.id}
                    onClick={() => toggling !== guest.id && handleRowClick(guest)}
                    className={`cursor-pointer border-b border-[#E5E8EB] transition-colors last:border-0 dark:border-gray-800 ${
                      guest.checked_in
                        ? 'bg-[#3182F6] hover:bg-[#2670E0] dark:bg-[#3182F6] dark:hover:bg-[#2670E0]'
                        : 'hover:bg-[#F2F4F6] dark:hover:bg-[#2C2C34]'
                    } ${toggling === guest.id ? 'opacity-50' : ''}`}
                  >
                    {/* 이름 */}
                    <td className="px-4 py-3">
                      <span
                        className={`text-body font-semibold ${
                          guest.checked_in ? 'text-white' : 'text-[#191F28] dark:text-white'
                        }`}
                      >
                        {guest.customer_name}
                      </span>
                    </td>

                    {/* 성별 */}
                    <td className="px-4 py-3 text-center">
                      {guest.gender ? (
                        <Badge
                          color={guest.gender === '남' ? 'info' : 'pink'}
                          size="sm"
                          className={guest.checked_in ? 'opacity-90' : ''}
                        >
                          {guest.gender}
                        </Badge>
                      ) : (
                        <span className={`text-label ${guest.checked_in ? 'text-white/60' : 'text-[#B0B8C1]'}`}>
                          -
                        </span>
                      )}
                    </td>

                    {/* 인원 */}
                    <td className="px-4 py-3 text-center">
                      {(guest.male_count != null || guest.female_count != null) ? (
                        <span className={`text-label tabular-nums ${guest.checked_in ? 'text-white/80' : 'text-[#4E5968] dark:text-gray-300'}`}>
                          {guest.male_count != null ? `남${guest.male_count}` : ''}
                          {guest.male_count != null && guest.female_count != null ? ' ' : ''}
                          {guest.female_count != null ? `여${guest.female_count}` : ''}
                        </span>
                      ) : (
                        <span className={`text-label ${guest.checked_in ? 'text-white/60' : 'text-[#B0B8C1]'}`}>
                          -
                        </span>
                      )}
                    </td>

                    {/* 입장 시간 */}
                    <td className="px-4 py-3 text-center">
                      <span
                        className={`text-label tabular-nums ${
                          guest.checked_in ? 'text-white font-semibold' : 'text-[#B0B8C1]'
                        }`}
                      >
                        {formatTime(guest.checked_in_at)}
                      </span>
                    </td>

                    {/* 상태 */}
                    <td className="px-4 py-3 text-center">
                      {toggling === guest.id ? (
                        <Spinner size="sm" />
                      ) : guest.checked_in ? (
                        <Badge color="success" size="sm">
                          입장 완료
                        </Badge>
                      ) : (
                        <Badge color="gray" size="sm">
                          미입장
                        </Badge>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* 입장 취소 확인 모달 */}
      <Modal
        show={cancelModal.open}
        size="md"
        popup
        onClose={() => setCancelModal({ open: false, guest: null })}
      >
        <ModalHeader />
        <ModalBody>
          <div className="flex flex-col items-center gap-4 text-center">
            <AlertTriangle size={48} className="text-[#FF9F00]" />
            <div>
              <h3 className="text-heading font-semibold text-[#191F28] dark:text-white">
                입장 취소 확인
              </h3>
              <p className="mt-2 text-body text-[#4E5968] dark:text-gray-300">
                <span className="font-semibold text-[#191F28] dark:text-white">
                  {cancelModal.guest?.customer_name}
                </span>
                님의 입장을 취소하시겠습니까?
              </p>
            </div>
            <div className="flex w-full gap-3">
              <Button
                color="light"
                className="flex-1"
                onClick={() => setCancelModal({ open: false, guest: null })}
              >
                닫기
              </Button>
              <Button
                color="failure"
                className="flex-1"
                onClick={handleCancelConfirm}
              >
                입장 취소
              </Button>
            </div>
          </div>
        </ModalBody>
      </Modal>
    </div>
  )
}
