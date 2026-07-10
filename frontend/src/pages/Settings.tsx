import { useEffect, useState } from 'react';
import { Wifi, WifiOff, RefreshCw } from 'lucide-react';
import { toast } from 'sonner';
import { settingsAPI } from '@/services/api';
import { useTenantStore } from '@/stores/tenant-store';
import { Card } from '@/components/ui/card';
import { Alert } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { Spinner } from '@/components/ui/spinner';
import { Button } from '@/components/ui/button';

interface NaverStatus {
  has_cookie: boolean;
  cookie_length: number;
  cookie_preview: string;
  is_valid: boolean | null;
  source: string;
  business_id: string;
}

export default function Settings() {
  const [status, setStatus] = useState<NaverStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [checking, setChecking] = useState(false);
  const { tenants, currentTenantId } = useTenantStore();
  const currentTenant = tenants.find(t => String(t.id) === currentTenantId);
  const hasUnstable = currentTenant?.has_unstable ?? false;
  const tenantLabel = currentTenant?.name || currentTenant?.slug || '네이버';

  // Unstable state
  const [unstableStatus, setUnstableStatus] = useState<NaverStatus | null>(null);
  const [unstableChecking, setUnstableChecking] = useState(false);
  const [unstableSaving, setUnstableSaving] = useState(false);
  const [unstableSyncing, setUnstableSyncing] = useState(false);
  const [unstableBusinessId, setUnstableBusinessId] = useState('');


  // silent=true: 스피너 표시 없음 (mount 의 Promise.all 에서 사용 — global loading 으로 처리)
  // silent=false (기본): 개별 checking 스피너 표시 (refresh 버튼 / 저장 후 재조회 시 사용)
  const fetchStatus = async (silent = false) => {
    if (!silent) setChecking(true);
    try {
      const res = await settingsAPI.getNaverStatus();
      setStatus(res.data);
    } catch {
      toast.error('상태 확인 실패');
    } finally {
      setChecking(false);
    }
  };

  const fetchUnstableStatus = async (silent = false) => {
    if (!silent) setUnstableChecking(true);
    try {
      const res = await settingsAPI.getUnstableStatus();
      setUnstableStatus(res.data);
      if (res.data.business_id && !unstableBusinessId) {
        setUnstableBusinessId(res.data.business_id);
      }
    } catch {
      // unstable 미설정 시 무시
    } finally {
      setUnstableChecking(false);
    }
  };


  useEffect(() => {
    // 둘 다 끝나야 loading=false. 빠른 쪽이 끝났다고 거짓 "로딩 완료" 표시되는 race 방지.
    Promise.all([fetchStatus(true), fetchUnstableStatus(true)])
      .finally(() => setLoading(false));
  }, []);

  // 쿠키는 UI 에서 입력하지 않는다 (반복 오입력 사고로 입력 UI 제거).
  // 네이버/언스테이블 쿠키는 DB 직접 UPDATE 또는 담당자 요청으로만 주입한다.
  // 관련 사고 이력·정책: docs / 쿠키 오입력 사고 메모.

  const handleSaveUnstable = async () => {
    if (!unstableBusinessId.trim()) {
      toast.error('Business ID를 입력해주세요');
      return;
    }
    setUnstableSaving(true);
    try {
      const res = await settingsAPI.updateUnstableSettings({ business_id: unstableBusinessId.trim() });
      if (res.data.success === false) {
        toast.error(res.data.message);
        return;
      }
      toast.success(res.data.message);
      if (res.data.warning) toast.warning(res.data.warning);
      await fetchUnstableStatus();
    } catch {
      toast.error('언스테이블 설정 저장 실패');
    } finally {
      setUnstableSaving(false);
    }
  };

  const handleSyncUnstable = async () => {
    setUnstableSyncing(true);
    try {
      const res = await settingsAPI.syncUnstable();
      if (res.data.success) {
        toast.success(res.data.message);
      } else {
        toast.error(res.data.message);
      }
    } catch {
      toast.error('언스테이블 동기화 실패');
    } finally {
      setUnstableSyncing(false);
    }
  };



  if (loading) {
    return (
      <div className="flex h-64 items-center justify-center">
        <Spinner size="lg" />
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      {/* Naver Connection Status */}
      <Card>
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold text-gray-900 dark:text-white">
            {tenantLabel} 네이버 연동
          </h2>
          <div className="flex items-center gap-2">
            {status?.is_valid === true && (
              <Badge color="success" icon={Wifi}>
                연결됨
              </Badge>
            )}
            {status?.is_valid === false && (
              <Badge color="failure" icon={WifiOff}>
                연결 끊김
              </Badge>
            )}
            {status?.is_valid === null && !status?.has_cookie && (
              <Badge color="gray">미설정</Badge>
            )}
            <Button
              size="xs"
              color="light"
              onClick={() => fetchStatus(false)}
              disabled={checking}
            >
              <RefreshCw size={14} className={checking ? 'animate-spin' : ''} />
            </Button>
          </div>
        </div>

        <div className="mt-3 space-y-2 text-sm text-gray-600 dark:text-gray-400">
          <div className="flex justify-between">
            <span>Business ID</span>
            <span className="font-mono">{status?.business_id}</span>
          </div>
          <div className="flex justify-between">
            <span>쿠키 소스</span>
            <span>{status?.source === 'runtime' ? '직접 입력 (런타임)' : '.env 파일'}</span>
          </div>
          <div className="flex justify-between">
            <span>쿠키 길이</span>
            <span>{status?.cookie_length || 0}자</span>
          </div>
        </div>

        {status?.is_valid === false && (
          <Alert color="failure" className="mt-4">
            쿠키가 만료되었습니다. 담당자에게 쿠키 갱신을 요청하세요. (쿠키는 DB에서 직접 관리합니다)
          </Alert>
        )}
      </Card>


      {/* Unstable Naver Connection Status */}
      {hasUnstable && <Card>
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold text-gray-900 dark:text-white">
            언스테이블 네이버 연동
          </h2>
          <div className="flex items-center gap-2">
            {unstableStatus?.is_valid === true && (
              <Badge color="success" icon={Wifi}>연결됨</Badge>
            )}
            {unstableStatus?.is_valid === false && (
              <Badge color="failure" icon={WifiOff}>연결 끊김</Badge>
            )}
            {(!unstableStatus || (unstableStatus?.is_valid === null && !unstableStatus?.has_cookie)) && (
              <Badge color="gray">미설정</Badge>
            )}
            <Button
              size="xs"
              color="light"
              onClick={() => fetchUnstableStatus()}
              disabled={unstableChecking}
            >
              <RefreshCw size={14} className={unstableChecking ? 'animate-spin' : ''} />
            </Button>
          </div>
        </div>

        {unstableStatus?.has_cookie && (
          <div className="mt-3 space-y-2 text-sm text-gray-600 dark:text-gray-400">
            <div className="flex justify-between">
              <span>Business ID</span>
              <span className="font-mono">{unstableStatus.business_id}</span>
            </div>
            <div className="flex justify-between">
              <span>쿠키 길이</span>
              <span>{unstableStatus.cookie_length || 0}자</span>
            </div>
          </div>
        )}

        {unstableStatus?.is_valid === false && (
          <Alert color="failure" className="mt-4">
            쿠키가 만료되었습니다. 담당자에게 쿠키 갱신을 요청하세요. (쿠키는 DB에서 직접 관리합니다)
          </Alert>
        )}
      </Card>}

      {/* Unstable Settings Input (Business ID only — 쿠키는 DB 직접 관리) */}
      {hasUnstable && <Card>
        <h2 className="text-lg font-semibold text-gray-900 dark:text-white">
          언스테이블 설정
        </h2>
        <p className="text-sm text-gray-500 dark:text-gray-400">
          언스테이블 네이버 스마트플레이스의 Business ID를 입력하세요. 쿠키는 DB에서 직접 관리합니다.
        </p>

        <div className="mt-3 space-y-3">
          <div>
            <label className="text-caption font-medium text-gray-700 dark:text-gray-300">Business ID</label>
            <input
              type="text"
              className="mt-1 w-full rounded-lg border border-gray-300 px-3 py-2 text-sm font-mono dark:border-gray-600 dark:bg-gray-800 dark:text-white"
              placeholder="1000256"
              value={unstableBusinessId}
              onChange={(e) => setUnstableBusinessId(e.target.value)}
            />
          </div>
        </div>

        <div className="mt-3 flex gap-2">
          <Button onClick={handleSaveUnstable} disabled={unstableSaving || !unstableBusinessId.trim()}>
            {unstableSaving ? <Spinner size="sm" className="mr-2" /> : null}
            저장 및 테스트
          </Button>
          {unstableStatus?.is_valid && (
            <Button color="light" onClick={handleSyncUnstable} disabled={unstableSyncing}>
              {unstableSyncing ? <Spinner size="sm" className="mr-2" /> : <RefreshCw size={14} className="mr-1.5" />}
              수동 동기화
            </Button>
          )}
        </div>
      </Card>}
    </div>
  );
}
