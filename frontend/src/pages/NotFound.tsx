import { useNavigate } from 'react-router-dom'
import { Compass } from 'lucide-react'
import { Button } from '@/components/ui/button'

export default function NotFound() {
  const navigate = useNavigate()
  return (
    <div className="flex min-h-[60vh] flex-col items-center justify-center gap-4 px-4 text-center">
      <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-[#F2F4F6] text-[#8B95A1] dark:bg-[#2C2C34] dark:text-gray-400">
        <Compass size={32} />
      </div>
      <div>
        <h1 className="text-title font-bold text-[#191F28] dark:text-white">페이지를 찾을 수 없습니다</h1>
        <p className="mt-2 text-label text-[#8B95A1] dark:text-gray-400">
          요청하신 주소가 잘못됐거나 더 이상 존재하지 않습니다.
        </p>
      </div>
      <div className="flex gap-2">
        <Button color="light" onClick={() => navigate(-1)}>
          이전으로
        </Button>
        <Button color="blue" onClick={() => navigate('/')}>
          메인으로
        </Button>
      </div>
    </div>
  )
}
