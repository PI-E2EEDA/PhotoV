/* eslint-disable */
/* tslint:disable */
// @ts-nocheck
/*
 * ---------------------------------------------------------------
 * ## THIS FILE WAS GENERATED VIA SWAGGER-TYPESCRIPT-API        ##
 * ##                                                           ##
 * ## AUTHOR: acacode                                           ##
 * ## SOURCE: https://github.com/acacode/swagger-typescript-api ##
 * ---------------------------------------------------------------
 */

/** MeasureType */
export enum MeasureType {
  Power = 'power',
  Energy = 'energy',
}

/** BearerResponse */
export interface BearerResponse {
  /** Access Token */
  access_token: string
  /** Token Type */
  token_type: string
}

/** Body_auth_api_bearer_db_auth_login_auth_login_post */
export interface BodyAuthApiBearerDbAuthLoginAuthLoginPost {
  /** Grant Type */
  grant_type?: string | null
  /** Username */
  username: string
  /**
   * Password
   * @format password
   */
  password: string
  /**
   * Scope
   * @default ""
   */
  scope?: string
  /** Client Id */
  client_id?: string | null
  /**
   * Client Secret
   * @format password
   */
  client_secret?: string | null
}

/** ErrorModel */
export interface ErrorModel {
  /** Detail */
  detail: string | Record<string, string>
}

/** HTTPValidationError */
export interface HTTPValidationError {
  /** Detail */
  detail?: ValidationError[]
}

/** SmartPlug */
export interface SmartPlug {
  /** Id */
  id?: number | null
  /** Name */
  name: string
  /** Installation Id */
  installation_id?: number | null
}

/** SmartPlugMeasure */
export interface SmartPlugMeasure {
  /** Id */
  id?: number | null
  /**
   * Time
   * @format date-time
   */
  time: string
  /** Value */
  value: number
  /** Smartplug Id */
  smartplug_id?: number | null
}

/** UserCreate */
export interface UserCreate {
  /**
   * Email
   * @format email
   */
  email: string
  /** Password */
  password: string
  /**
   * Is Active
   * @default true
   */
  is_active?: boolean | null
  /**
   * Is Superuser
   * @default false
   */
  is_superuser?: boolean | null
  /**
   * Is Verified
   * @default false
   */
  is_verified?: boolean | null
}

/** UserRead */
export interface UserRead {
  /** Id */
  id: number
  /**
   * Email
   * @format email
   */
  email: string
  /**
   * Is Active
   * @default true
   */
  is_active?: boolean
  /**
   * Is Superuser
   * @default false
   */
  is_superuser?: boolean
  /**
   * Is Verified
   * @default false
   */
  is_verified?: boolean
}

/** ValidationError */
export interface ValidationError {
  /** Location */
  loc: (string | number)[]
  /** Message */
  msg: string
  /** Error Type */
  type: string
  /** Input */
  input?: any
  /** Context */
  ctx?: object
}

export type QueryParamsType = Record<string | number, any>
export type ResponseFormat = keyof Omit<Body, 'body' | 'bodyUsed'>

export interface FullRequestParams extends Omit<RequestInit, 'body'> {
  /** set parameter to `true` for call `securityWorker` for this request */
  secure?: boolean
  /** request path */
  path: string
  /** content type of request body */
  type?: ContentType
  /** query params */
  query?: QueryParamsType
  /** format of response (i.e. response.json() -> format: "json") */
  format?: ResponseFormat
  /** request body */
  body?: unknown
  /** base url */
  baseUrl?: string
  /** request cancellation token */
  cancelToken?: CancelToken
}

export type RequestParams = Omit<FullRequestParams, 'body' | 'method' | 'query' | 'path'>

export interface ApiConfig<SecurityDataType = unknown> {
  baseUrl?: string
  baseApiParams?: Omit<RequestParams, 'baseUrl' | 'cancelToken' | 'signal'>
  securityWorker?: (
    securityData: SecurityDataType | null,
  ) => Promise<RequestParams | void> | RequestParams | void
  customFetch?: typeof fetch
}

export interface HttpResponse<D extends unknown, E extends unknown = unknown> extends Response {
  data: D
  error: E
}

type CancelToken = Symbol | string | number

export enum ContentType {
  Json = 'application/json',
  JsonApi = 'application/vnd.api+json',
  FormData = 'multipart/form-data',
  UrlEncoded = 'application/x-www-form-urlencoded',
  Text = 'text/plain',
}

export class HttpClient<SecurityDataType = unknown> {
  public baseUrl: string = ''
  private securityData: SecurityDataType | null = null
  private securityWorker?: ApiConfig<SecurityDataType>['securityWorker']
  private abortControllers = new Map<CancelToken, AbortController>()
  private customFetch = (...fetchParams: Parameters<typeof fetch>) => fetch(...fetchParams)

  private baseApiParams: RequestParams = {
    credentials: 'same-origin',
    headers: {},
    redirect: 'follow',
    referrerPolicy: 'no-referrer',
  }

  constructor(apiConfig: ApiConfig<SecurityDataType> = {}) {
    Object.assign(this, apiConfig)
  }

  public setSecurityData = (data: SecurityDataType | null) => {
    this.securityData = data
  }

  protected encodeQueryParam(key: string, value: any) {
    const encodedKey = encodeURIComponent(key)
    return `${encodedKey}=${encodeURIComponent(typeof value === 'number' ? value : `${value}`)}`
  }

  protected addQueryParam(query: QueryParamsType, key: string) {
    return this.encodeQueryParam(key, query[key])
  }

  protected addArrayQueryParam(query: QueryParamsType, key: string) {
    const value = query[key]
    return value.map((v: any) => this.encodeQueryParam(key, v)).join('&')
  }

  protected toQueryString(rawQuery?: QueryParamsType): string {
    const query = rawQuery || {}
    const keys = Object.keys(query).filter((key) => 'undefined' !== typeof query[key])
    return keys
      .map((key) =>
        Array.isArray(query[key])
          ? this.addArrayQueryParam(query, key)
          : this.addQueryParam(query, key),
      )
      .join('&')
  }

  protected addQueryParams(rawQuery?: QueryParamsType): string {
    const queryString = this.toQueryString(rawQuery)
    return queryString ? `?${queryString}` : ''
  }

  private contentFormatters: Record<ContentType, (input: any) => any> = {
    [ContentType.Json]: (input: any) =>
      input !== null && (typeof input === 'object' || typeof input === 'string')
        ? JSON.stringify(input)
        : input,
    [ContentType.JsonApi]: (input: any) =>
      input !== null && (typeof input === 'object' || typeof input === 'string')
        ? JSON.stringify(input)
        : input,
    [ContentType.Text]: (input: any) =>
      input !== null && typeof input !== 'string' ? JSON.stringify(input) : input,
    [ContentType.FormData]: (input: any) => {
      if (input instanceof FormData) {
        return input
      }

      return Object.keys(input || {}).reduce((formData, key) => {
        const property = input[key]
        formData.append(
          key,
          property instanceof Blob
            ? property
            : typeof property === 'object' && property !== null
              ? JSON.stringify(property)
              : `${property}`,
        )
        return formData
      }, new FormData())
    },
    [ContentType.UrlEncoded]: (input: any) => this.toQueryString(input),
  }

  protected mergeRequestParams(params1: RequestParams, params2?: RequestParams): RequestParams {
    return {
      ...this.baseApiParams,
      ...params1,
      ...(params2 || {}),
      headers: {
        ...(this.baseApiParams.headers || {}),
        ...(params1.headers || {}),
        ...((params2 && params2.headers) || {}),
      },
    }
  }

  protected createAbortSignal = (cancelToken: CancelToken): AbortSignal | undefined => {
    if (this.abortControllers.has(cancelToken)) {
      const abortController = this.abortControllers.get(cancelToken)
      if (abortController) {
        return abortController.signal
      }
      return void 0
    }

    const abortController = new AbortController()
    this.abortControllers.set(cancelToken, abortController)
    return abortController.signal
  }

  public abortRequest = (cancelToken: CancelToken) => {
    const abortController = this.abortControllers.get(cancelToken)

    if (abortController) {
      abortController.abort()
      this.abortControllers.delete(cancelToken)
    }
  }

  public request = async <T = any, E = any>({
    body,
    secure,
    path,
    type,
    query,
    format,
    baseUrl,
    cancelToken,
    ...params
  }: FullRequestParams): Promise<HttpResponse<T, E>> => {
    const secureParams =
      ((typeof secure === 'boolean' ? secure : this.baseApiParams.secure) &&
        this.securityWorker &&
        (await this.securityWorker(this.securityData))) ||
      {}
    const requestParams = this.mergeRequestParams(params, secureParams)
    const queryString = query && this.toQueryString(query)
    const payloadFormatter = this.contentFormatters[type || ContentType.Json]
    const responseFormat = format || requestParams.format

    return this.customFetch(
      `${baseUrl || this.baseUrl || ''}${path}${queryString ? `?${queryString}` : ''}`,
      {
        ...requestParams,
        headers: {
          ...(requestParams.headers || {}),
          ...(type && type !== ContentType.FormData ? { 'Content-Type': type } : {}),
        },
        signal: (cancelToken ? this.createAbortSignal(cancelToken) : requestParams.signal) || null,
        body: typeof body === 'undefined' || body === null ? null : payloadFormatter(body),
      },
    ).then(async (response) => {
      const r = response as HttpResponse<T, E>
      r.data = null as unknown as T
      r.error = null as unknown as E

      const responseToParse = responseFormat ? response.clone() : response
      const data = !responseFormat
        ? r
        : await responseToParse[responseFormat]()
            .then((data) => {
              if (r.ok) {
                r.data = data
              } else {
                r.error = data
              }
              return r
            })
            .catch((e) => {
              r.error = e
              return r
            })

      if (cancelToken) {
        this.abortControllers.delete(cancelToken)
      }

      if (!response.ok) throw data
      return data
    })
  }
}

/**
 * @title FastAPI
 * @version 0.1.0
 */
export class Api<SecurityDataType extends unknown> extends HttpClient<SecurityDataType> {
  /**
   * No description
   *
   * @name RootGet
   * @summary Root
   * @request GET:/
   */
  rootGet = (params: RequestParams = {}) =>
    this.request<any, any>({
      path: `/`,
      method: 'GET',
      format: 'json',
      ...params,
    })

  auth = {
    /**
     * No description
     *
     * @tags auth
     * @name AuthApiBearerDbAuthLoginAuthLoginPost
     * @summary Auth:Api Bearer Db Auth.Login
     * @request POST:/auth/login
     */
    authApiBearerDbAuthLoginAuthLoginPost: (
      data: BodyAuthApiBearerDbAuthLoginAuthLoginPost,
      params: RequestParams = {},
    ) =>
      this.request<BearerResponse, ErrorModel | HTTPValidationError>({
        path: `/auth/login`,
        method: 'POST',
        body: data,
        type: ContentType.UrlEncoded,
        format: 'json',
        ...params,
      }),

    /**
     * No description
     *
     * @tags auth
     * @name AuthApiBearerDbAuthLogoutAuthLogoutPost
     * @summary Auth:Api Bearer Db Auth.Logout
     * @request POST:/auth/logout
     * @secure
     */
    authApiBearerDbAuthLogoutAuthLogoutPost: (params: RequestParams = {}) =>
      this.request<any, void>({
        path: `/auth/logout`,
        method: 'POST',
        secure: true,
        format: 'json',
        ...params,
      }),

    /**
     * No description
     *
     * @tags auth
     * @name RegisterRegisterAuthRegisterPost
     * @summary Register:Register
     * @request POST:/auth/register
     */
    registerRegisterAuthRegisterPost: (data: UserCreate, params: RequestParams = {}) =>
      this.request<UserRead, ErrorModel | HTTPValidationError>({
        path: `/auth/register`,
        method: 'POST',
        body: data,
        type: ContentType.Json,
        format: 'json',
        ...params,
      }),
  }
  measures = {
    /**
     * @description Get measures of power or energy
     *
     * @name GetMeasuresMeasuresInstallationIdTypeGet
     * @summary Get Measures
     * @request GET:/measures/{installation_id}/{type}
     * @secure
     */
    getMeasuresMeasuresInstallationIdTypeGet: (
      installationId: number,
      type: MeasureType,
      query?: {
        /**
         * Ascending
         * @default false
         */
        ascending?: boolean
        /**
         * Limit
         * @default 5760
         */
        limit?: number
        /**
         * Offset
         * @default 0
         */
        offset?: number
      },
      params: RequestParams = {},
    ) =>
      this.request<any, HTTPValidationError>({
        path: `/measures/${installationId}/${type}`,
        method: 'GET',
        query: query,
        secure: true,
        format: 'json',
        ...params,
      }),
  }
  smartplugs = {
    /**
     * @description Create a new smartplug with a name
     *
     * @name CreateSmartplugSmartplugsPost
     * @summary Create Smartplug
     * @request POST:/smartplugs/
     * @secure
     */
    createSmartplugSmartplugsPost: (data: SmartPlug, params: RequestParams = {}) =>
      this.request<any, HTTPValidationError>({
        path: `/smartplugs/`,
        method: 'POST',
        body: data,
        secure: true,
        type: ContentType.Json,
        format: 'json',
        ...params,
      }),

    /**
     * @description Send one power measure from a given smart-plug
     *
     * @name SendSmartplugMeasureSmartplugsInstallationIdPost
     * @summary Send Smartplug Measure
     * @request POST:/smartplugs/{installation_id}/
     * @secure
     */
    sendSmartplugMeasureSmartplugsInstallationIdPost: (
      installationId: number,
      data: SmartPlugMeasure,
      params: RequestParams = {},
    ) =>
      this.request<any, HTTPValidationError>({
        path: `/smartplugs/${installationId}/`,
        method: 'POST',
        body: data,
        secure: true,
        type: ContentType.Json,
        format: 'json',
        ...params,
      }),
  }
}
