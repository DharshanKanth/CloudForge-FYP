import { describe, it, expect } from 'vitest'
import { terraformApi } from '../api'

describe('API client', () => {
  it('builds downloadUrl relative when API_BASE_URL is empty', () => {
    // The module sets API_BASE_URL to '' by default in our changes.
    const url = terraformApi.downloadUrl('proj123')
    expect(url).toContain('/api/projects/proj123/terraform/download')
  })
})
