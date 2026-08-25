// Mirrors apps.core.responses.envelope / error_envelope — the DRF API's
// response shape everywhere in this project.
export type Envelope<T> = {
  success: boolean;
  data: T | null;
  message: string | null;
  errors: string[] | null;
};

export type Paginated<T> = {
  results: T[];
  pagination: {
    page: number;
    page_size: number;
    total_pages: number;
    total_count: number;
    next: string | null;
    previous: string | null;
  };
};

export type CurrentUser = {
  public_id: string;
  email: string;
  first_name: string;
  last_name: string;
  organization_id: number | null;
  mfa_enabled: boolean;
  roles: string[];
};
