export const processUploadAPI = "http://127.0.0.1:8000/process-test/processes/"

export const processViewsAPI = "https://sensors-test.protonintelligence.io/process/view_processes/"

export const processIdAPI = "http://127.0.0.1:8000/process-test/get_processes/"

export const batchEncoderAPI = "https://sensors-test.protonintelligence.io/sensors/electrode-create/"

export const userInfoAPI = 'https://sensors-test.protonintelligence.io/users/user_info/'

export const logoutUserAPI = 'https://sensors-test.protonintelligence.io/users/logout/'

export const batchDetailAPI = 'http://127.0.0.1:8000/test/v4/detail/' 

// Function to generate the full URL for retrieving electrode details
export function retrieveBatchDetailURL(batchLocation, batchId) {
    return `${batchDetailAPI}${batchLocation}/${batchId}/`;
}

export const updateBatchAPI = 'http://127.0.0.1:8000/test/v4/update/' 

// Function to generate the full URL for updating batch
//export function batchUpdateUrl(batchLocation, batchId) {
//    return `${updateBatchAPI}${batchLocation}/${batchId}/`
//}

export const batchListAPI = 'https://sensors-test.protonintelligence.io/sensors/v2/batches/'

export const elecImgAPI = 'https://sensors-test.protonintelligence.io/sensors/filtered-elecview-detail/'

export function electrodeURL(batchLocation, batchId, waferID, sensorID) {
    return `${elecImgAPI}${batchLocation}/${batchId}/${waferID}/${sensorID}/`;
}

export const testBatchEncoderAPI = 'https://sensors-test.protonintelligence.io/sensors/electrodes/create/'

export const taskStatusAPI = 'https://sensors-test.protonintelligence.io/sensors/electrodes/taskStatus/'

export const testBatchEncoderAPI2 = 'http://127.0.0.1:8000/test/batch/';

export const testBatchEncoderAPI3 = 'http://127.0.0.1:8000/test/v2/batch/';

export const testAsyncBatchEncoderAPI = 'http://127.0.0.1:8000/test/api/batch-encoder-async/';

export const updateBatchAPIv5 = 'http://127.0.0.1:8000/test/v5/batch/';

// Function to generate the full URL for updating batch
export function batchUpdateUrl(batchLocation, batchId) {
    return `${updateBatchAPIv5}${batchLocation}/${batchId}/`
}

export const updateSensorAPIv2 = 'http://127.0.0.1:8000/test/v2/sensors/';

export const v2BatchEncoderAPI = 'http://127.0.0.1:8000/batch-encoder/sensors/';

export const v3BatchEncoderAPI = 'http://127.0.0.1:8000/batch-encoder/v2/sensors/';

