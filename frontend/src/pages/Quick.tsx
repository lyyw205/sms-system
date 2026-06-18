import { useEffect, useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Home, Search, Wrench } from 'lucide-react';
import { toast } from 'sonner';

import { roomsAPI } from '@/services/api';
import { queryKeys } from '@/lib/queryKeys';
import { useTenantStore } from '@/stores/tenant-store';

import { Table, TableHead, TableBody, TableRow, TableHeadCell, TableCell } from '@/components/ui/table';
import { TextInput } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { Spinner } from '@/components/ui/spinner';
import { Button } from '@/components/ui/button';

import UnifiedRoomEditModal from './Quick/UnifiedRoomEditModal';

interface QuickRoom {
  id: number;
  room_number: string;
  room_type: string;
  grade?: number | null;
  building_name?: string | null;
  naver_biz_item_id?: string | null;
  biz_item_ids?: string[];
}

interface QuickBizItem {
  biz_item_id: string;
  name: string;
  exposed?: boolean;
}

export default function Quick() {
  // 테넌트 전환 시 리렌더 → queryKey 재생성.
  useTenantStore((s) => s.currentTenantId);

  const [search, setSearch] = useState('');
  const [editRoomId, setEditRoomId] = useState<number | null>(null);
  const [modalOpen, setModalOpen] = useState(false);

  const roomsQuery = useQuery<QuickRoom[]>({
    queryKey: queryKeys.rooms.listWithInactive(),
    queryFn: () => roomsAPI.getAll({ include_inactive: true }).then((r) => r.data),
    staleTime: 300_000,
  });
  const rooms = roomsQuery.data ?? [];
  const loading = roomsQuery.isFetching;

  const bizItemsQuery = useQuery<QuickBizItem[]>({
    queryKey: queryKeys.rooms.bizItems(),
    queryFn: () => roomsAPI.getBizItems().then((r) => r.data),
    staleTime: 300_000,
  });
  const bizItems = bizItemsQuery.data ?? [];

  useEffect(() => {
    if (roomsQuery.error) {
      toast.error('객실 목록 로드 실패');
    }
  }, [roomsQuery.error]);

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    if (!q) return rooms;
    return rooms.filter(
      (r) =>
        r.room_number.toLowerCase().includes(q) ||
        r.room_type.toLowerCase().includes(q) ||
        (r.building_name ?? '').toLowerCase().includes(q),
    );
  }, [rooms, search]);

  const bizLabel = (room: QuickRoom): string[] => {
    const ids = room.biz_item_ids && room.biz_item_ids.length > 0
      ? room.biz_item_ids
      : room.naver_biz_item_id
        ? [room.naver_biz_item_id]
        : [];
    return ids.map((id) => {
      const item = bizItems.find((b) => b.biz_item_id === id);
      return item ? (item.exposed === false ? `[미노출] ${item.name}` : item.name) : id;
    });
  };

  const openEdit = (roomId: number) => {
    setEditRoomId(roomId);
    setModalOpen(true);
  };

  return (
    <div className="space-y-6">
      {/* 헤더 */}
      <div>
        <div className="flex items-center gap-2.5">
          <div className="stat-icon bg-[#E8F3FF] text-[#3182F6] dark:bg-[#3182F6]/15 dark:text-[#3182F6]">
            <Wrench size={20} />
          </div>
          <div>
            <h1 className="page-title">객실 통합 편집(Quick)</h1>
            <p className="page-subtitle">URL 전용 페이지입니다. 객실+상품 메타를 한 화면에서 편집합니다.</p>
          </div>
        </div>
      </div>

      <div className="section-card">
        {/* 검색 바 */}
        <div className="filter-bar border-b border-[#E5E8EB] dark:border-gray-800">
          <div className="w-full max-w-xs">
            <TextInput
              icon={Search}
              placeholder="객실번호 / 타입 / 건물 검색"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
          </div>
          {rooms.length > 0 && (
            <Badge color="info" size="sm">{filtered.length} / {rooms.length}</Badge>
          )}
        </div>

        {loading ? (
          <div className="flex items-center justify-center py-16">
            <Spinner size="lg" />
          </div>
        ) : filtered.length === 0 ? (
          <div className="empty-state">
            <Home size={40} strokeWidth={1} />
            <p className="text-body">{rooms.length === 0 ? '등록된 객실이 없습니다' : '검색 결과가 없습니다'}</p>
          </div>
        ) : (
          <Table hoverable striped>
            <TableHead>
              <TableRow>
                <TableHeadCell className="text-center">객실</TableHeadCell>
                <TableHeadCell className="text-center">타입</TableHeadCell>
                <TableHeadCell className="text-center">건물</TableHeadCell>
                <TableHeadCell className="text-center">등급</TableHeadCell>
                <TableHeadCell className="text-center">연결 상품</TableHeadCell>
                <TableHeadCell className="text-center">작업</TableHeadCell>
              </TableRow>
            </TableHead>
            <TableBody className="divide-y">
              {filtered.map((room) => {
                const labels = bizLabel(room);
                return (
                  <TableRow key={room.id}>
                    <TableCell className="text-center font-semibold text-[#191F28] dark:text-white">
                      {room.room_number}
                    </TableCell>
                    <TableCell>
                      <div className="flex justify-center">
                        <Badge color="gray">{room.room_type}</Badge>
                      </div>
                    </TableCell>
                    <TableCell className="text-center">
                      {room.building_name ? (
                        <Badge color="gray" size="sm">{room.building_name}</Badge>
                      ) : (
                        <span className="text-caption text-[#B0B8C1] dark:text-gray-600">-</span>
                      )}
                    </TableCell>
                    <TableCell className="text-center">
                      {typeof room.grade === 'number' ? (
                        <Badge color="info" size="sm">{room.grade}</Badge>
                      ) : (
                        <span className="text-caption text-[#B0B8C1] dark:text-gray-600">미설정</span>
                      )}
                    </TableCell>
                    <TableCell>
                      {labels.length === 0 ? (
                        <div className="flex justify-center">
                          <span className="text-caption text-[#B0B8C1] dark:text-gray-600">-</span>
                        </div>
                      ) : (
                        <div className="flex flex-wrap justify-center gap-1">
                          {labels.map((label, i) => (
                            <Badge key={i} color="info" size="xs">{label}</Badge>
                          ))}
                        </div>
                      )}
                    </TableCell>
                    <TableCell className="text-center">
                      <div className="flex justify-center">
                        <Button color="light" size="xs" onClick={() => openEdit(room.id)}>
                          <Wrench className="mr-1.5 h-3.5 w-3.5" />
                          통합 편집
                        </Button>
                      </div>
                    </TableCell>
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        )}
      </div>

      <UnifiedRoomEditModal
        show={modalOpen}
        roomId={editRoomId}
        onClose={() => setModalOpen(false)}
        onSaved={() => {
          roomsQuery.refetch();
          bizItemsQuery.refetch();
        }}
      />
    </div>
  );
}
