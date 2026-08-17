import { Link } from 'react-router-dom';
import { cn } from '@/lib/utils';

const MARK = '/brand/blueseatra-mark.png';
const LOCKUP = '/brand/blueseatra-lockup.png';

export function BrandLogo({
  variant = 'lockup',
  to = '/',
  className,
  imgClassName,
}) {
  const src = variant === 'mark' ? MARK : LOCKUP;
  const img = (
    <img
      src={src}
      alt="Blueseatra"
      className={cn(
        variant === 'mark' ? 'h-8 w-8 object-contain' : 'h-8 w-auto max-w-[168px] object-contain object-left',
        imgClassName,
      )}
    />
  );
  if (to === false) {
    return <span className={cn('inline-flex items-center', className)}>{img}</span>;
  }
  return (
    <Link to={to} className={cn('inline-flex items-center', className)} aria-label="Blueseatra">
      {img}
    </Link>
  );
}
