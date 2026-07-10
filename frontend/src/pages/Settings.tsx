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

  // Unstable state (읽기전용 상태 표시만 유지 — 입력 UI 없음)
  const [unstableStatus, setUnstableStatus] = useState<NaverStatus | null>(null);
  const [unstableChecking, setUnstableChecking] = useState(false);


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

  // 쿠키·Business ID 등 네이버 연동 설정은 UI 에서 입력하지 않는다 (반복 오입력 사고로 입력 UI 제거).
  // 네이버/언스테이블 쿠키·설정은 DB 직접 UPDATE 또는 담당자 요청으로만 주입한다.
  // 이 페이지는 읽기전용 연결 상태만 보여준다.


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


      {/* Unstable Naver Connection Status (읽기전용) */}
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
    </div>
  );
}
